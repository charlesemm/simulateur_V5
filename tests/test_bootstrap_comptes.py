"""Vérifie la réinitialisation de mot de passe en ligne de commande.

Un compte administrateur verrouillé n'a aucun recours par l'API : c'est cette
commande qui le rouvre. Elle doit donc être sûre.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.database import async_session_factory
from auth.bootstrap import _reinitialiser
from auth.models import User
from auth.security import hash_password, verify_password


async def _compte(email: str) -> User:
    async with async_session_factory() as session:
        return (await session.execute(
            select(User).where(User.email == email)
        )).scalar_one()


async def test_la_reinitialisation_remplace_le_mot_de_passe(administrateur):
    del administrateur

    await _reinitialiser("admin@cnam.ci", "NouveauMotDePasse1")

    compte = await _compte("admin@cnam.ci")
    assert verify_password("NouveauMotDePasse1", compte.mot_de_passe_hash)
    assert not verify_password("MotDePasseAdmin1", compte.mot_de_passe_hash)


async def test_le_nom_d_utilisateur_est_accepte_comme_identifiant(administrateur):
    """La commande doit retrouver un compte comme le fait la connexion."""

    del administrateur

    await _reinitialiser("ADMIN", "NouveauMotDePasse2")

    compte = await _compte("admin@cnam.ci")
    assert verify_password("NouveauMotDePasse2", compte.mot_de_passe_hash)


async def test_la_reinitialisation_reactive_un_compte_desactive(administrateur):
    """Un compte désactivé refuse la connexion même avec le bon mot de passe."""

    del administrateur

    async with async_session_factory() as session:
        compte = (await session.execute(
            select(User).where(User.email == "admin@cnam.ci")
        )).scalar_one()
        compte.statut_actif = False
        compte.doit_changer_mot_de_passe = True
        await session.commit()

    await _reinitialiser("admin@cnam.ci", "NouveauMotDePasse3")

    compte = await _compte("admin@cnam.ci")
    assert compte.statut_actif is True
    assert compte.doit_changer_mot_de_passe is False


async def test_un_identifiant_inconnu_ne_touche_a_rien(administrateur):
    del administrateur
    empreinte = (await _compte("admin@cnam.ci")).mot_de_passe_hash

    await _reinitialiser(f"inconnu-{uuid.uuid4().hex}", "PeuImporte12")

    assert (await _compte("admin@cnam.ci")).mot_de_passe_hash == empreinte


async def test_le_compte_reinitialise_se_connecte_par_l_api(client_api, administrateur):
    """Le vrai critère : la connexion passe après la réinitialisation."""

    del administrateur
    await _reinitialiser("admin@cnam.ci", "MotDePasseRendu1")

    reponse = await client_api.post("/auth/login", json={
        "identifiant": "admin@cnam.ci",
        "mot_de_passe": "MotDePasseRendu1",
    })

    assert reponse.status_code == 200
    assert reponse.json()["role"] == "administrateur"
    assert reponse.json()["doit_changer_mot_de_passe"] is False


async def test_l_ancien_mot_de_passe_ne_passe_plus(client_api, administrateur):
    del administrateur
    await _reinitialiser("admin@cnam.ci", "MotDePasseRendu2")

    reponse = await client_api.post("/auth/login", json={
        "identifiant": "admin@cnam.ci",
        "mot_de_passe": "MotDePasseAdmin1",
    })

    assert reponse.status_code == 401


async def test_le_journal_distingue_les_trois_motifs_de_refus(
    client_api, administrateur, caplog
):
    """La réponse au client reste identique ; le serveur, lui, dit laquelle.

    Sans cette trace, un refus de connexion est indiagnosticable : impossible
    de savoir si le compte n'existe pas, s'il est désactivé, ou si le mot de
    passe est faux.
    """

    with caplog.at_level("WARNING", logger="api.routers.auth"):
        await client_api.post("/auth/login", json={
            "identifiant": "compte-qui-n-existe-pas", "mot_de_passe": "peu importe",
        })
        await client_api.post("/auth/login", json={
            "identifiant": administrateur.email, "mot_de_passe": "mauvais mot de passe",
        })

    messages = " | ".join(enregistrement.message for enregistrement in caplog.records)
    assert "aucun compte ne porte cet identifiant" in messages
    assert "le mot de passe ne correspond pas" in messages


async def test_le_client_n_apprend_jamais_quel_compte_existe(client_api, administrateur):
    """Les deux refus doivent être indiscernables vus du navigateur."""

    inconnu = await client_api.post("/auth/login", json={
        "identifiant": "compte-qui-n-existe-pas", "mot_de_passe": "x",
    })
    mauvais = await client_api.post("/auth/login", json={
        "identifiant": administrateur.email, "mot_de_passe": "x",
    })

    assert inconnu.status_code == mauvais.status_code == 401
    assert inconnu.json() == mauvais.json()


async def test_un_hachage_reste_illisible(administrateur):
    """On ne stocke jamais le mot de passe, seulement son empreinte."""

    del administrateur
    await _reinitialiser("admin@cnam.ci", "MotDePasseRendu3")

    compte = await _compte("admin@cnam.ci")
    assert "MotDePasseRendu3" not in compte.mot_de_passe_hash
    assert compte.mot_de_passe_hash.startswith("$2b$")
    assert compte.mot_de_passe_hash != hash_password("MotDePasseRendu3")
