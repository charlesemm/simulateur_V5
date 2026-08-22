"""Vérifie les moteurs MDM, entrepôt et gouvernance.

Ce que chacun doit prouver : le MDM sait dire quelles paires sont vraies,
l'entrepôt creuse l'historique sans jamais faire se recouvrir deux périodes,
et la gouvernance signale les tables dont personne ne répond.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import InsuredPerson, InsuredProfession, InsuredRight
from entrepot import approfondir_historique
from gouvernance import inventaire, rapport, volumetrie
from mdm import evaluer, generer_variantes, lire_paires
from mdm.models import MdmPair
from simulation.runs import ouvrir_execution


# ── T2 : rapprochement d'identités ───────────────────────────────────────

async def test_les_variantes_sont_creees_avec_leur_verite_terrain(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    resume = await generer_variantes(simulation_id, nombre=2, part_leurres=0.0, graine=1)

    assert resume["paires"] == 2
    assert resume["leurres"] == 0

    paires = await lire_paires(simulation_id)
    assert len(paires) == 2
    assert all(paire.meme_personne for paire in paires)

    async with async_session_factory() as session:
        # Les variantes s'ajoutent au référentiel : deux assurés au départ.
        total = (await session.execute(
            select(func.count()).select_from(InsuredPerson)
        )).scalar_one()
    assert total == 4


async def test_les_leurres_ne_sont_pas_la_meme_personne(base_vierge):
    del base_vierge
    await generer_variantes(None, nombre=2, part_leurres=1.0, graine=1)

    paires = await lire_paires()

    assert paires
    assert all(paire.meme_personne is False for paire in paires)
    assert all(paire.type_variation == "HOMONYME" for paire in paires)


async def test_un_rapprochement_parfait_obtient_cent_pour_cent(base_vierge):
    del base_vierge
    await generer_variantes(None, nombre=2, part_leurres=0.0, graine=1)
    paires = await lire_paires()

    note = await evaluer(
        [(str(paire.personne_uuid_source), str(paire.personne_uuid_variante))
         for paire in paires]
    )

    assert note["vrais_positifs"] == 2
    assert note["faux_positifs"] == 0
    assert note["faux_negatifs"] == 0
    assert note["precision_pourcent"] == 100.0
    assert note["rappel_pourcent"] == 100.0


async def test_rapprocher_les_leurres_fait_chuter_la_precision(base_vierge):
    """C'est à cela que servent les leurres : punir qui rapproche tout."""

    del base_vierge
    await generer_variantes(None, nombre=2, part_leurres=0.0, graine=1)
    await generer_variantes(None, nombre=2, part_leurres=1.0, graine=2)
    paires = await lire_paires()

    note = await evaluer(
        [(str(paire.personne_uuid_source), str(paire.personne_uuid_variante))
         for paire in paires]
    )

    assert note["faux_positifs"] >= 1
    assert note["precision_pourcent"] < 100.0
    assert note["rappel_pourcent"] == 100.0


async def test_l_ordre_des_paires_est_sans_importance(base_vierge):
    del base_vierge
    await generer_variantes(None, nombre=1, part_leurres=0.0, graine=1)
    paire = (await lire_paires())[0]

    inversee = await evaluer(
        [(str(paire.personne_uuid_variante), str(paire.personne_uuid_source))]
    )

    assert inversee["vrais_positifs"] == 1


async def test_une_paire_inconnue_est_ecartee_du_calcul(base_vierge):
    """ÉCHO ne juge que ce qu'il a lui-même fabriqué."""

    del base_vierge
    import uuid

    await generer_variantes(None, nombre=1, part_leurres=0.0, graine=1)

    note = await evaluer([(str(uuid.uuid4()), str(uuid.uuid4()))])

    assert note["hors_perimetre"] == 1
    assert note["vrais_positifs"] == 0
    assert note["faux_positifs"] == 0


# ── T3 : entrepôt de données ─────────────────────────────────────────────

async def test_l_historique_ajoute_des_mois_de_droits(base_vierge):
    del base_vierge
    resume = await approfondir_historique(mois=6, assures=2, graine=1)

    assert resume["mois_demandes"] == 6
    assert resume["droits_ecrits"] >= 6

    async with async_session_factory() as session:
        total = (await session.execute(
            select(func.count()).select_from(InsuredRight)
        )).scalar_one()

    # Deux droits existaient déjà pour le mois courant.
    assert total >= 2 + resume["droits_ecrits"]


async def test_l_historique_ne_recree_pas_un_mois_deja_present(base_vierge):
    del base_vierge
    premier = await approfondir_historique(mois=3, assures=2, graine=1)
    second = await approfondir_historique(mois=3, assures=2, graine=1)

    assert premier["droits_ecrits"] > 0
    assert second["droits_ecrits"] == 0


async def test_les_periodes_de_profession_ne_se_recouvrent_pas(base_vierge):
    """La contrainte d'exclusion de la migration 0007 est le juge de paix."""

    del base_vierge
    await approfondir_historique(mois=2, assures=2, graine=7)

    async with async_session_factory() as session:
        periodes = list((await session.execute(
            select(InsuredProfession).order_by(InsuredProfession.profession_date_debut)
        )).scalars())

    # Une période fermée doit l'être après son début.
    for periode in periodes:
        if periode.profession_date_fin is not None:
            assert periode.profession_date_fin > periode.profession_date_debut

    # Au plus une période ouverte par assuré et par code.
    ouvertes = [periode for periode in periodes if periode.profession_date_fin is None]
    clefs = [(periode.personne_uuid, periode.profession_code) for periode in ouvertes]
    assert len(clefs) == len(set(clefs))


async def test_un_historique_de_zero_mois_est_refuse(base_vierge):
    del base_vierge
    with pytest.raises(ValueError):
        await approfondir_historique(mois=0)


# ── T4 : gouvernance ─────────────────────────────────────────────────────

async def test_l_inventaire_signale_les_tables_sans_proprietaire(base_vierge):
    del base_vierge
    etat = await inventaire()

    assert etat["tables_declarees"] > 0
    assert etat["tables_en_base"] > 0
    # Le dépôt compte plus de tables que le catalogue n'en déclare : la
    # gouvernance doit le dire plutôt que de le taire.
    assert etat["sans_proprietaire"]
    assert "TB_REF_ASSURES" in etat["tables_a_donnees_personnelles"]
    assert etat["declarees_absentes"] == []


async def test_la_volumetrie_compte_les_lignes_du_catalogue(base_vierge):
    del base_vierge
    lignes = await volumetrie()

    assures = next(ligne for ligne in lignes if ligne["table"] == "TB_REF_ASSURES")

    assert assures["lignes"] == 2
    assert assures["proprietaire"]
    assert assures["donnees_personnelles"] is True


async def test_le_rapport_reprend_les_violations_de_la_qualite(base_vierge):
    del base_vierge
    from app.models import Agent

    async with async_session_factory() as session:
        agent = await session.get(Agent, "AG0001")
        agent.agent_email = "pas_un_email_valide"
        await session.commit()

    etat = await rapport()

    codes = {violation["regle"] for violation in etat["violations"]}
    assert "EMAIL_AGENT_INVALIDE" in codes
    assert etat["total_violations"] >= 1
    assert etat["lignage"]
    assert etat["couverture_catalogue_pourcent"] > 0


async def test_l_api_expose_les_trois_moteurs(client_api):
    simulation_id = await ouvrir_execution({"vitesse": 60})

    generation = await client_api.post(
        "/mdm/generer",
        json={"simulation_id": str(simulation_id), "nombre": 2, "part_leurres": 0.0},
    )
    assert generation.status_code == 200
    assert generation.json()["paires"] == 2

    verite = await client_api.get(f"/mdm/verite-terrain?simulation_id={simulation_id}")
    assert verite.status_code == 200
    paires = verite.json()
    assert len(paires) == 2

    note = await client_api.post(
        "/mdm/evaluer",
        json={
            "simulation_id": str(simulation_id),
            "paires": [
                [paire["personne_uuid_source"], paire["personne_uuid_variante"]]
                for paire in paires
            ],
        },
    )
    assert note.status_code == 200
    assert note.json()["rappel_pourcent"] == 100.0

    historique = await client_api.post(
        "/entrepot/historique", json={"mois": 3, "assures": 2}
    )
    assert historique.status_code == 200
    assert historique.json()["droits_ecrits"] > 0

    gouvernance = await client_api.get("/gouvernance/rapport")
    assert gouvernance.status_code == 200
    assert "lignage" in gouvernance.json()


async def test_lancer_un_run_mdm_fabrique_sa_verite_terrain(client_api):
    """Le type choisi doit changer ce que l'exécution produit, dès son ouverture."""

    demarrage = await client_api.post(
        "/simulation/start",
        json={"type_simulation": "MDM", "vitesse": 3600, "nombre_passages_simultanes_max": 1},
    )
    assert demarrage.status_code == 202
    simulation_id = demarrage.json()["simulation_id"]
    await client_api.post("/simulation/stop")

    paires = await lire_paires(simulation_id)

    assert paires
    assert all(str(paire.simulation_id) == simulation_id for paire in paires)


async def test_la_purge_des_donnees_ne_doit_pas_emporter_la_verite_terrain(base_vierge):
    """Une paire survit à la disparition de l'assuré qu'elle décrit."""

    del base_vierge
    await generer_variantes(None, nombre=1, part_leurres=0.0, graine=1)
    paire = (await lire_paires())[0]

    async with async_session_factory() as session:
        variante = await session.get(InsuredPerson, paire.personne_uuid_variante)
        await session.delete(variante)
        await session.commit()

    async with async_session_factory() as session:
        survivante = await session.get(MdmPair, paire.paire_id)

    assert survivante is not None
