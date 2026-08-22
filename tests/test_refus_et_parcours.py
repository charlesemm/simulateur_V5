"""Vérifie le registre des refus (X5) et la diffusion du parcours (X4)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import Invoice
from events import DomainEvent, EventBus
from events import publish_simulation_event
from realtime.parcours_consumer import ParcoursConsumer
from simulation.models import RefusAccueil
from simulation.passage import PassageSimulation
from simulation.purge import purger
from simulation.runs import ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT, ASSURE_SANS_DROITS


class FauxServeur:
    """Recueille ce qui aurait été diffusé aux navigateurs."""

    def __init__(self) -> None:
        self.envois: list[tuple[str, dict]] = []

    async def emit(self, evenement: str, payload: dict, namespace: str) -> None:
        del namespace
        self.envois.append((evenement, payload))


# ── X5 : registre des refus ──────────────────────────────────────────────

async def test_un_refus_a_l_accueil_est_consigne(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    await PassageSimulation(
        ASSURE_SANS_DROITS, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    async with async_session_factory() as session:
        refus = (await session.execute(select(RefusAccueil))).scalars().all()
        factures = (await session.execute(
            select(func.count()).select_from(Invoice)
        )).scalar_one()

    assert len(refus) == 1
    assert refus[0].refus_motif == "droits_fermes"
    assert refus[0].personne_uuid == ASSURE_SANS_DROITS
    assert refus[0].simulation_id == simulation_id
    # Le refus ne crée toujours aucune facture : c'est la règle métier.
    assert factures == 0


async def test_un_passage_accepte_ne_laisse_aucun_refus(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    async with async_session_factory() as session:
        refus = (await session.execute(select(func.count()).select_from(RefusAccueil))).scalar_one()

    assert refus == 0


async def test_la_purge_emporte_aussi_les_refus(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await PassageSimulation(
        ASSURE_SANS_DROITS, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    supprimees = await purger(simulation_id)

    assert supprimees["refus_accueil"] == 1
    async with async_session_factory() as session:
        reste = (await session.execute(select(func.count()).select_from(RefusAccueil))).scalar_one()
    assert reste == 0


async def test_l_api_liste_les_refus_et_les_compte(client_api):
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await PassageSimulation(
        ASSURE_SANS_DROITS, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    liste = await client_api.get(f"/simulation/executions/{simulation_id}/refus")
    assert liste.status_code == 200
    assert len(liste.json()) == 1
    assert liste.json()[0]["refus_motif"] == "droits_fermes"

    fiche = await client_api.get(f"/simulation/executions/{simulation_id}")
    assert fiche.json()["volumetrie"]["refus_accueil"] == 1


# ── X4 : diffusion du parcours ───────────────────────────────────────────

async def test_les_evenements_sont_diffuses_tels_quels():
    """Le terminal doit recevoir les vrais événements, pas des déductions."""

    bus = EventBus()
    serveur = FauxServeur()
    consommateur = ParcoursConsumer(bus, serveur, fenetre_secondes=0.05)
    await consommateur.start()
    try:
        await bus.publish(DomainEvent(
            event_type="facture.creee", passage_id="abc123",
            simulated_at=datetime.now(timezone.utc),
            payload={"facture_numero": "FAC-1"}, simulation_id=None,
        ))
        await asyncio.sleep(0.2)
    finally:
        await consommateur.stop()

    assert serveur.envois
    nom, payload = serveur.envois[0]
    assert nom == "parcours:evenements"
    assert payload["evenements"][0]["type"] == "facture.creee"
    assert payload["evenements"][0]["passage_id"] == "abc123"
    assert payload["evenements"][0]["payload"]["facture_numero"] == "FAC-1"
    assert payload["ecartes"] == 0


async def test_une_rafale_est_plafonnee_et_le_reste_annonce():
    """Cent événements en une fenêtre ne doivent pas partir d'un bloc."""

    bus = EventBus()
    serveur = FauxServeur()
    consommateur = ParcoursConsumer(bus, serveur, fenetre_secondes=0.1, plafond=5)
    await consommateur.start()
    try:
        maintenant = datetime.now(timezone.utc)
        for rang in range(30):
            await bus.publish(DomainEvent(
                event_type="prestation.servie", passage_id=f"p{rang}",
                simulated_at=maintenant, payload={}, simulation_id=None,
            ))
        await asyncio.sleep(0.3)
    finally:
        await consommateur.stop()

    total_diffuses = sum(len(payload["evenements"]) for _, payload in serveur.envois)
    total_ecartes = sum(payload["ecartes"] for _, payload in serveur.envois)

    assert total_diffuses <= 10
    assert total_diffuses + total_ecartes == 30


async def test_les_deux_consommateurs_recoivent_chacun_leur_copie():
    """Le relais du parcours ne doit pas priver le calcul des KPI."""

    bus = EventBus()
    premiere = await bus.subscribe()
    seconde = await bus.subscribe()

    await bus.publish(DomainEvent(
        event_type="facture.creee", passage_id="abc",
        simulated_at=datetime.now(timezone.utc), payload={}, simulation_id=None,
    ))

    assert premiere.qsize() == 1
    assert seconde.qsize() == 1
