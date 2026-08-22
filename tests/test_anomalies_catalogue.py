"""Vérifie le réglage type par type et le journal des injections.

Le catalogue est ce qui permet de demander une anomalie sans demander les
autres ; le journal est la vérité terrain à laquelle se compareront le moteur
de qualité des données et le MDM.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from anomalies.catalogue import (
    CATALOGUE_INITIAL, DATE_ANTIDATEE, MONTANT_ABERRANT, QUANTITE_EXCESSIVE,
)
from anomalies.config import AnomaliesConfig, Reglage
from anomalies.models import AnomalyInjection, AnomalyType
from anomalies.repository import (
    charger_catalogue, enregistrer_injections, modifier_type,
)
from app.database import async_session_factory
from events import publish_simulation_event
from simulation.passage import PassageSimulation
from simulation.runs import ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT

REFERENCE = Decimal("10000")


def config(**options) -> AnomaliesConfig:
    """Fabrique une configuration déterministe pour les tests."""

    return AnomaliesConfig(seed=1234, **options)


def test_un_type_desactive_est_seul_a_se_taire():
    """Couper les dates ne doit pas couper les montants."""

    anomalies = config(enabled=True, rate=1.0)
    anomalies.reglages[DATE_ANTIDATEE] = Reglage(active=False)

    from datetime import date

    jour = date(2026, 8, 22)
    assert anomalies.injecter_date(jour) == jour
    assert anomalies.injecter_montant(REFERENCE) != REFERENCE


def test_chaque_type_porte_son_propre_taux():
    """Un taux nul sur un type le fait taire, quel que soit le taux global."""

    anomalies = config(enabled=True, rate=1.0)
    anomalies.reglages[QUANTITE_EXCESSIVE] = Reglage(taux=0.0)

    for _ in range(50):
        assert anomalies.injecter_quantite(2, 2) == 2
    assert anomalies.injecter_montant(REFERENCE) != REFERENCE


def test_sans_taux_propre_le_type_suit_le_taux_global():
    """C'est le comportement d'avant le catalogue, qui doit être préservé."""

    anomalies = config(enabled=True, rate=0.0)
    assert anomalies.taux_effectif(MONTANT_ABERRANT) == 0.0
    for _ in range(50):
        assert anomalies.injecter_montant(REFERENCE) == REFERENCE


def test_le_contexte_retient_la_valeur_d_origine():
    """Le journal doit permettre de mesurer l'écart, pas seulement de le voir."""

    anomalies = config(enabled=True, rate=1.0)
    contexte = anomalies.contexte(passage_id="abc123")
    faussee = contexte.injecter_montant(REFERENCE, "FAC-0001")

    injection = contexte.injections[0]
    assert injection.anomalie_code == MONTANT_ABERRANT
    assert injection.valeur_origine == str(REFERENCE)
    assert injection.valeur_injectee == str(faussee)
    assert injection.cible_cle == "FAC-0001"
    assert injection.passage_id == "abc123"

    # Vider rend le carnet et le remet à zéro.
    assert len(contexte.vider()) == 1
    assert contexte.injections == []


def test_rien_n_est_retenu_quand_rien_n_est_injecte():
    anomalies = config(enabled=False, rate=1.0)
    contexte = anomalies.contexte()
    assert contexte.injecter_montant(REFERENCE) == REFERENCE
    assert contexte.injections == []


async def test_le_catalogue_est_installe_par_la_migration(base_vierge):
    """Les cinq types doivent être en base dès la première migration."""

    del base_vierge
    async with async_session_factory() as session:
        codes = {ligne.anomalie_code for ligne in (
            await session.execute(select(AnomalyType))
        ).scalars()}

    assert codes == {type_anomalie.code for type_anomalie in CATALOGUE_INITIAL}


async def test_modifier_un_type_change_la_base_et_la_memoire(base_vierge):
    del base_vierge
    from anomalies.config import anomalies_config

    modifie = await modifier_type(MONTANT_ABERRANT, active=False, taux=0.5)

    assert modifie.anomalie_active is False
    assert modifie.anomalie_taux == Decimal("0.50")
    assert anomalies_config.reglages[MONTANT_ABERRANT].active is False
    assert anomalies_config.reglages[MONTANT_ABERRANT].taux == 0.5

    # Le chargement au démarrage doit retrouver le même réglage.
    anomalies_config.reglages[MONTANT_ABERRANT] = Reglage()
    await charger_catalogue()
    assert anomalies_config.reglages[MONTANT_ABERRANT].active is False


async def test_le_passage_consigne_ses_anomalies(base_vierge):
    """Un passage à 100 % laisse au journal des lignes rattachées à son run."""

    del base_vierge
    from anomalies.config import anomalies_config

    simulation_id = await ouvrir_execution({"vitesse": 60})
    anomalies_config.enabled = True
    anomalies_config.rate = 1.0
    try:
        await PassageSimulation(
            ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
            publish_simulation_event, 7, simulation_id,
        ).run()
    finally:
        anomalies_config.enabled = False
        anomalies_config.rate = 0.0

    async with async_session_factory() as session:
        injections = (await session.execute(select(AnomalyInjection))).scalars().all()

    assert injections
    assert all(ligne.simulation_id == simulation_id for ligne in injections)
    assert all(ligne.passage_id for ligne in injections)
    assert {DATE_ANTIDATEE, MONTANT_ABERRANT} <= {
        ligne.anomalie_code for ligne in injections
    }


async def test_le_journal_reste_vide_sans_anomalie(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    async with async_session_factory() as session:
        injections = (await session.execute(select(AnomalyInjection))).scalars().all()

    assert injections == []


async def test_enregistrer_une_liste_vide_ne_touche_pas_la_base(base_vierge):
    del base_vierge
    assert await enregistrer_injections([]) == 0
