"""Vérifie qu'une exécution est enregistrée et marque les lignes produites.

Sans ce rattachement, rien ne permet de dire quelle exécution a créé quelle
ligne : la volumétrie par exécution, la purge sélective et la vérité terrain
du MDM reposent toutes dessus.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, InvoiceStatus
from events.models import EventJournal
from events import publish_simulation_event
from simulation.models import STATUT_ARRETEE, STATUT_EN_COURS, SimulationRun
from simulation.passage import PassageSimulation
from simulation.runs import cloturer_execution, ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT


async def test_l_execution_est_ouverte_puis_cloturee(base_vierge):
    """Le cycle complet d'une exécution laisse une ligne exploitable."""

    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60, "graine": 7})

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)
        assert execution.simulation_statut == STATUT_EN_COURS
        assert execution.simulation_date_fin is None
        assert execution.simulation_parametres["vitesse"] == 60

    await cloturer_execution(simulation_id, STATUT_ARRETEE, reussis=3, echoues=1)

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)

    assert execution.simulation_statut == STATUT_ARRETEE
    assert execution.simulation_date_fin is not None
    assert (execution.passages_reussis, execution.passages_echoues) == (3, 1)


async def test_les_lignes_produites_portent_l_execution(base_vierge):
    """Facture, prestation, statuts et journal remontent tous à l'exécution."""

    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60, "graine": 7})

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()
        prestation = (await session.execute(select(InvoiceProvision))).scalars().first()
        statuts = (await session.execute(select(InvoiceStatus))).scalars().all()
        evenements = (await session.execute(select(EventJournal))).scalars().all()

    assert facture.simulation_id == simulation_id
    assert prestation.simulation_id == simulation_id
    assert statuts and all(statut.simulation_id == simulation_id for statut in statuts)
    assert evenements and all(
        evenement.simulation_id == simulation_id for evenement in evenements
    )


async def test_un_passage_sans_execution_reste_orphelin(base_vierge):
    """Un lancement hors API produit des lignes à NULL, jamais une erreur."""

    del base_vierge
    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7,
    ).run()

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()

    assert facture.simulation_id is None


async def test_cloturer_une_execution_inconnue_ne_leve_pas(base_vierge):
    """La clôture est tolérante : l'arrêt du moteur ne doit jamais échouer."""

    del base_vierge
    await cloturer_execution(uuid.uuid4(), STATUT_ARRETEE, reussis=0, echoues=0)


async def test_la_fiche_compte_ce_que_l_execution_a_produit(client_api):
    """L'écran Simulations lit cette fiche : elle doit compter juste."""

    simulation_id = await ouvrir_execution({"vitesse": 60})
    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id,
    ).run()

    reponse = await client_api.get(f"/simulation/executions/{simulation_id}")
    assert reponse.status_code == 200
    fiche = reponse.json()

    assert fiche["execution"]["simulation_id"] == str(simulation_id)
    assert fiche["volumetrie"]["factures"] == 1
    assert fiche["volumetrie"]["prestations"] >= 1
    assert fiche["volumetrie"]["evenements"] > 0
    # Aucune anomalie n'est active dans la base de test.
    assert fiche["volumetrie"]["anomalies"] == 0
    assert fiche["anomalies_par_type"] == {}


async def test_la_fiche_d_une_execution_inconnue_est_introuvable(client_api):
    reponse = await client_api.get(f"/simulation/executions/{uuid.uuid4()}")
    assert reponse.status_code == 404


async def test_l_api_ouvre_une_execution_au_nom_de_l_utilisateur(
    client_api, administrateur
):
    """Le démarrage par l'API nomme le lanceur et rend l'identifiant."""

    demarrage = await client_api.post(
        "/simulation/start", json={"vitesse": 1000, "nombre_passages_simultanes_max": 1}
    )
    assert demarrage.status_code == 202
    simulation_id = demarrage.json()["simulation_id"]
    assert simulation_id is not None

    arret = await client_api.post("/simulation/stop")
    assert arret.status_code == 200

    executions = await client_api.get("/simulation/executions")
    assert executions.status_code == 200
    ligne = executions.json()[0]

    assert ligne["simulation_id"] == simulation_id
    assert ligne["simulation_statut"] == STATUT_ARRETEE
    assert ligne["utilisateur_uuid"] == str(administrateur.utilisateur_uuid)
    assert ligne["simulation_parametres"]["passages_simultanes_max"] == 1
