"""Vérifie ce que les écrans W4 à W8 consomment : données, exports et purge."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, InvoiceStatus, PriorAuthorization
from events import publish_simulation_event
from events.models import EventJournal
from simulation.passage import PassageSimulation
from simulation.purge import compter, purger
from simulation.runs import ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT


async def jouer(simulation_id, seed: int = 7) -> None:
    """Exécute un passage complet rattaché à une exécution."""

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, seed, simulation_id,
    ).run()


# ── W5 : consultation des données ────────────────────────────────────────

async def test_la_recherche_d_assures_filtre_sur_le_nom(client_api):
    reponse = await client_api.get("/assures?recherche=Kouassi")

    assert reponse.status_code == 200
    resultat = reponse.json()
    assert resultat["total"] == 1
    assert resultat["assures"][0]["nom"] == "Kouassi"
    assert resultat["assures"][0]["droits_ouverts"] is True


async def test_la_liste_des_assures_est_paginee(client_api):
    reponse = await client_api.get("/assures?limite=1")

    resultat = reponse.json()
    assert resultat["total"] == 2
    assert len(resultat["assures"]) == 1


async def test_la_fiche_d_un_assure_montre_ses_droits(client_api):
    reponse = await client_api.get(f"/assures/{ASSURE_COUVERT}")

    assert reponse.status_code == 200
    fiche = reponse.json()
    assert fiche["nom"] == "Kouassi"
    assert fiche["droits"]
    assert fiche["droits"][0]["ouverts"] is True
    assert fiche["professions"]


async def test_la_fiche_d_un_assure_inconnu_est_introuvable(client_api):
    reponse = await client_api.get(f"/assures/{uuid.uuid4()}")
    assert reponse.status_code == 404


# ── W4 : qualité, taux demandé contre taux constaté ──────────────────────

async def test_le_rapport_expose_le_taux_demande(client_api):
    """L'écran Qualité compare ce qui a été demandé à ce qui a été fait."""

    from anomalies.catalogue import MONTANT_ABERRANT

    simulation_id = await ouvrir_execution(
        {"vitesse": 60, "anomalies": {MONTANT_ABERRANT: {"taux": 0.4}}}
    )
    await jouer(simulation_id)

    reponse = await client_api.get(
        f"/qualite/rapport?simulation_id={simulation_id}&inclure_referentiel=false"
    )

    ligne = next(
        valeur for valeur in reponse.json()["confrontation"]
        if valeur["anomalie_code"] == MONTANT_ABERRANT
    )
    assert ligne["taux_demande_pourcent"] == 40.0


# ── W6 : exports par période et par exécution ────────────────────────────

async def test_l_export_par_periode_est_produit(client_api):
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)

    reponse = await client_api.post(
        "/reports/periode?date_min=2026-01-01&date_max=2030-12-31"
    )

    assert reponse.status_code == 200
    assert reponse.json()["excel"].endswith(".xlsx")


async def test_une_periode_inversee_est_refusee(client_api):
    reponse = await client_api.post(
        "/reports/periode?date_min=2030-01-01&date_max=2026-01-01"
    )
    assert reponse.status_code == 422


async def test_l_export_d_une_execution_produit_les_deux_fichiers(client_api):
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)

    reponse = await client_api.post(f"/reports/execution/{simulation_id}")

    assert reponse.status_code == 200
    fichiers = reponse.json()
    assert fichiers["pdf"].endswith(".pdf")
    assert fichiers["excel"].endswith(".xlsx")


async def test_l_export_d_une_execution_inconnue_est_refuse(client_api):
    reponse = await client_api.post(f"/reports/execution/{uuid.uuid4()}")
    assert reponse.status_code == 404


# ── W8 : volumétrie et purge ─────────────────────────────────────────────

async def test_la_previsualisation_compte_sans_rien_supprimer(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)

    apercu = await compter(simulation_id)

    assert apercu["factures"] == 1
    assert apercu["evenements"] > 0

    async with async_session_factory() as session:
        restantes = (await session.execute(
            select(func.count()).select_from(Invoice)
        )).scalar_one()
    assert restantes == 1


async def test_la_purge_efface_tout_ce_que_l_execution_a_produit(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})
    # Une graine qui déclenche une entente préalable, pour éprouver le cycle
    # facture-entente que la purge doit rompre avant de supprimer.
    for graine in range(1, 6):
        await jouer(simulation_id, seed=graine)

    supprimees = await purger(simulation_id)

    assert supprimees["total"] > 0
    async with async_session_factory() as session:
        for modele in (Invoice, InvoiceProvision, InvoiceStatus,
                       PriorAuthorization, EventJournal):
            reste = (await session.execute(
                select(func.count()).select_from(modele)
            )).scalar_one()
            assert reste == 0, modele.__name__


async def test_la_purge_conserve_l_execution_elle_meme(base_vierge):
    """Le statut et les compteurs restent l'historique de ce qui a eu lieu."""

    del base_vierge
    from simulation.models import SimulationRun

    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)
    await purger(simulation_id)

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)

    assert execution is not None


async def test_la_purge_epargne_les_autres_executions(base_vierge):
    del base_vierge
    premiere = await ouvrir_execution({"vitesse": 60})
    seconde = await ouvrir_execution({"vitesse": 60})
    await jouer(premiere, seed=1)
    await jouer(seconde, seed=2)

    await purger(premiere)

    async with async_session_factory() as session:
        restantes = list((await session.execute(select(Invoice))).scalars())

    assert len(restantes) == 1
    assert restantes[0].simulation_id == seconde


async def test_la_purge_d_une_execution_inconnue_est_refusee(client_api):
    reponse = await client_api.request(
        "DELETE", f"/simulation/executions/{uuid.uuid4()}/donnees"
    )
    assert reponse.status_code == 404


async def test_l_api_previsualise_puis_purge(client_api):
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)

    apercu = await client_api.get(f"/simulation/executions/{simulation_id}/purge")
    assert apercu.status_code == 200
    assert apercu.json()["factures"] == 1

    purge = await client_api.request(
        "DELETE", f"/simulation/executions/{simulation_id}/donnees"
    )
    assert purge.status_code == 200
    assert purge.json()["factures"] == 1

    fiche = await client_api.get(f"/simulation/executions/{simulation_id}")
    assert fiche.json()["volumetrie"]["factures"] == 0
