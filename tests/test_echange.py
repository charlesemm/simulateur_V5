"""M6 — Le canal API : transmission d'une campagne à l'outil testé.

Ce que ces tests protègent : un échange rate toujours pour l'une des trois
raisons du cahier — jamais autrement — et aucune des trois ne se lit comme
« l'outil n'a rien détecté ».
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from api.main import fastapi_app
from campagnes import creer, historique, lancer, lire, transmettre
from campagnes.echange import _classer_rapport
from campagnes.models import (
    MOTIF_RAPPORT_MALFORME, MOTIF_RAPPORT_SANS_DETAIL, MOTIF_SILENCE,
    RESULTAT_ECHEC, RESULTAT_SUCCES, STATUT_ECHEC_ECHANGE, STATUT_RAPPORT_RECU,
)

pytestmark = pytest.mark.asyncio


def _client_interne() -> httpx.AsyncClient:
    """Un client attaché directement à l'application, sans port réseau.

    C'est ce qui permet de faire tourner le témoin en boucle fermée dans les
    tests : `campagnes/echange.py` accepte ce client à la place d'un vrai
    client HTTP, exactement pour cet usage.
    """

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app), base_url="http://interne",
    )


async def _campagne_generee(**reglages) -> uuid.UUID:
    campagne = await creer(graine=101, volume_cible=20, anomalies=reglages or None)
    suivi = await lancer(campagne.campagne_id)
    for _ in range(200):
        if suivi.terminee:
            break
        await asyncio.sleep(0.02)
    assert suivi.terminee, "La génération n'a pas fini à temps."
    return campagne.campagne_id


# ── La classification d'un rapport, en direct ────────────────────────────

async def test_un_corps_qui_n_est_pas_un_objet_est_malforme():
    motif, constats, message = _classer_rapport(["pas", "un", "objet"])

    assert motif == MOTIF_RAPPORT_MALFORME
    assert constats == []
    assert message


async def test_un_rapport_sans_la_cle_constats_est_sans_detail():
    motif, _constats, _message = _classer_rapport({"resume": {"detectees": 3}})

    assert motif == MOTIF_RAPPORT_SANS_DETAIL


async def test_des_constats_qui_ne_sont_pas_une_liste_sont_malformes():
    motif, _constats, _message = _classer_rapport({"constats": "pas une liste"})

    assert motif == MOTIF_RAPPORT_MALFORME


async def test_un_constat_sans_numero_de_ligne_est_malforme():
    motif, _constats, _message = _classer_rapport({"constats": [{"champ": "X"}]})

    assert motif == MOTIF_RAPPORT_MALFORME


async def test_un_rapport_valide_meme_vide_est_exploitable():
    motif, constats, message = _classer_rapport({"constats": []})

    assert motif is None
    assert constats == []
    assert message is None


# ── Le canal, de bout en bout, contre le témoin ──────────────────────────

async def test_transmettre_au_temoin_reussit(base_vierge):
    campagne_id = await _campagne_generee(MONTANT_ABERRANT={"taux": 0.5})

    async with _client_interne() as client:
        echange = await transmettre(
            campagne_id, "http://interne/temoin/analyser", client=client
        )

    assert echange.echange_resultat == RESULTAT_SUCCES
    assert echange.echange_motif_echec is None
    assert echange.echange_date_reception is not None
    assert echange.echange_nombre_constats > 0
    assert echange.echange_rapport is not None

    campagne = await lire(campagne_id)
    assert campagne.campagne_statut == STATUT_RAPPORT_RECU

    passes = await historique(campagne_id)
    assert [passe.echange_id for passe in passes] == [echange.echange_id]


async def test_l_outil_qui_ne_repond_pas_est_un_silence(base_vierge):
    campagne_id = await _campagne_generee(MONTANT_ABERRANT={"taux": 0.5})

    async with _client_interne() as client:
        echange = await transmettre(
            campagne_id, "http://interne/route-inexistante", client=client
        )

    assert echange.echange_resultat == RESULTAT_ECHEC
    assert echange.echange_motif_echec == MOTIF_SILENCE
    assert echange.echange_nombre_constats == 0
    # Un échec d'échange n'est jamais un score de 0 % : rien n'a été noté.
    assert echange.echange_rapport is None

    campagne = await lire(campagne_id)
    assert campagne.campagne_statut == STATUT_ECHEC_ECHANGE


async def test_un_rapport_sans_detail_n_est_pas_un_echec_de_format(base_vierge):
    campagne_id = await _campagne_generee(MONTANT_ABERRANT={"taux": 0.5})

    async with _client_interne() as client:
        echange = await transmettre(
            campagne_id, "http://interne/temoin/analyser-resume", client=client
        )

    assert echange.echange_resultat == RESULTAT_ECHEC
    assert echange.echange_motif_echec == MOTIF_RAPPORT_SANS_DETAIL


async def test_transmettre_une_campagne_non_generee_est_refuse(base_vierge):
    campagne = await creer()

    with pytest.raises(RuntimeError):
        await transmettre(campagne.campagne_id)


async def test_transmettre_une_campagne_inconnue_est_refuse(base_vierge):
    with pytest.raises(LookupError):
        await transmettre(uuid.uuid4())


# ── Vu de l'écran ─────────────────────────────────────────────────────────

async def test_api_liste_les_motifs_echec(client_api, base_vierge):
    reponse = await client_api.get("/campagnes/motifs-echec")

    assert reponse.status_code == 200
    assert set(reponse.json()) == {
        "silence", "rapport_malforme", "rapport_sans_detail",
    }


async def test_api_transmet_une_campagne_dont_l_outil_ne_repond_pas(
    client_api, base_vierge
):
    """Sans rien qui écoute à l'adresse donnée, le canal dit « silence »,
    jamais « 0 % détecté » — vu depuis l'écran, pas depuis le module."""

    creation = await client_api.post(
        "/campagnes", json={"volume_cible": 100, "graine": 55}
    )
    campagne_id = creation.json()["campagne_id"]
    lancement = await client_api.post(f"/campagnes/{campagne_id}/generer")
    assert lancement.status_code == 202

    for _ in range(200):
        suivi = (await client_api.get(f"/campagnes/{campagne_id}/progression")).json()
        if suivi["terminee"]:
            break
        await asyncio.sleep(0.02)
    assert suivi["terminee"], suivi

    transmission = await client_api.post(
        f"/campagnes/{campagne_id}/transmettre",
        # Port réservé, quasi certain de n'écouter nulle part : le test reste
        # le même que le poste porte ou non un serveur sur le port par défaut.
        json={"adresse": "http://127.0.0.1:1/inconnu"},
    )
    assert transmission.status_code == 201, transmission.text
    corps = transmission.json()
    assert corps["echange_resultat"] == "echec"
    assert corps["echange_motif_echec"] == "silence"
    assert corps["echange_adresse"] == "http://127.0.0.1:1/inconnu"

    echanges = (await client_api.get(f"/campagnes/{campagne_id}/echanges")).json()
    assert len(echanges) == 1
    assert echanges[0]["echange_id"] == corps["echange_id"]


async def test_api_refuse_de_transmettre_une_campagne_non_generee(
    client_api, base_vierge
):
    creation = await client_api.post("/campagnes", json={})
    campagne_id = creation.json()["campagne_id"]

    transmission = await client_api.post(f"/campagnes/{campagne_id}/transmettre")

    assert transmission.status_code == 409


async def test_api_transmettre_une_campagne_inconnue(client_api, base_vierge):
    transmission = await client_api.post(
        f"/campagnes/{uuid.uuid4()}/transmettre"
    )

    assert transmission.status_code == 404
