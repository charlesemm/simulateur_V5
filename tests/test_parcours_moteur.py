"""Vérifie les règles métier du moteur : droits, régime et montants.

Ce sont les régressions les plus coûteuses : une facture ouverte sans droits,
ou un taux qui ne suit pas le régime, fausse tout ce qui est calculé ensuite.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, InvoiceStatus
from simulation.events import SimulationEvent
from simulation.passage import PassageSimulation
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT, ASSURE_SANS_DROITS

pytest_plugins = ()


class Collecteur:
    """Capture les événements émis, en lieu et place du bus."""

    def __init__(self) -> None:
        self.evenements: list[SimulationEvent] = []

    async def __call__(self, evenement: SimulationEvent) -> None:
        self.evenements.append(evenement)

    def types(self) -> list[str]:
        return [evenement.event_type for evenement in self.evenements]


async def jouer(insured_id, seed: int = 7) -> Collecteur:
    """Exécute un passage complet à vitesse maximale."""

    collecteur = Collecteur()
    passage = PassageSimulation(
        insured_id, DEFAULT_CONFIG, lambda: 1_000_000.0, collecteur, seed
    )
    await passage.run()
    return collecteur


async def test_sans_droits_aucune_facture_n_est_ouverte(base_vierge):
    del base_vierge
    collecteur = await jouer(ASSURE_SANS_DROITS)

    assert collecteur.types() == ["passage.refuse"]
    assert collecteur.evenements[0].payload["motif"] == "droits_fermes"

    async with async_session_factory() as session:
        factures = (await session.execute(select(Invoice))).scalars().all()
    assert factures == []


async def test_avec_droits_la_facture_est_ouverte_puis_cloturee(base_vierge):
    del base_vierge
    collecteur = await jouer(ASSURE_COUVERT)

    types = collecteur.types()
    assert types[0] == "facture.creee"
    assert "prestation.servie" in types

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()
        statuts = [ligne.statut_code for ligne in (await session.execute(
            select(InvoiceStatus).where(InvoiceStatus.facture_numero == facture.facture_numero)
            .order_by(InvoiceStatus.statut_date_debut)
        )).scalars()]

    assert "ouverte" in statuts
    assert "cloturee" in statuts
    assert "rejetee" not in statuts


async def test_la_facture_porte_le_regime_de_l_assure(base_vierge):
    """L'assuré couvert est au régime RGB : la facture doit suivre, à 70 %."""

    del base_vierge
    await jouer(ASSURE_COUVERT)

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()

    assert facture.regime_code == "RGB"
    assert facture.regime_taux == Decimal("70.00")
    # « CMU » nomme le dispositif, jamais un régime.
    assert facture.regime_code != "CMU"


async def test_les_montants_se_repartissent_selon_le_taux(base_vierge):
    del base_vierge
    await jouer(ASSURE_COUVERT)

    async with async_session_factory() as session:
        prestation = (await session.execute(select(InvoiceProvision))).scalars().first()

    base = prestation.prestation_base_remboursement
    assert prestation.prestation_taux_remboursement == Decimal("70.00")
    assert prestation.prestation_montant_rq == base * Decimal("0.70")
    assert prestation.prestation_montant_assure == base - prestation.prestation_montant_rq
    # La colonne restait vide avant la correction du chantier R2.
    assert prestation.prestation_montant_rq is not None


async def test_un_regime_a_cent_pour_cent_ne_laisse_rien_a_charge(base_vierge):
    """On bascule l'assuré couvert en RAM et on rejoue le même passage."""

    del base_vierge
    from app.models import InsuredPerson

    async with async_session_factory() as session:
        assure = await session.get(InsuredPerson, ASSURE_COUVERT)
        assure.regime_code = "RAM"
        await session.commit()

    await jouer(ASSURE_COUVERT)

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()
        prestation = (await session.execute(select(InvoiceProvision))).scalars().first()

    assert facture.regime_taux == Decimal("100.00")
    assert prestation.prestation_montant_assure == Decimal("0.00")


async def test_le_passage_est_reproductible(base_vierge):
    """Deux passages de même graine doivent produire la même suite d'étapes."""

    del base_vierge
    premier = await jouer(ASSURE_COUVERT, seed=99)

    async with async_session_factory() as session:
        for facture in (await session.execute(select(Invoice))).scalars().all():
            await session.delete(facture)
        await session.commit()

    second = await jouer(ASSURE_COUVERT, seed=99)
    assert premier.types() == second.types()
