"""Vérifie que le navigateur peut joindre l'API depuis un poste de travail.

Un préflight refusé bloque la requête avant qu'elle parte : côté navigateur,
c'est indiscernable d'une API éteinte. Ce cas a coûté une soirée de recherche
sur un mot de passe qui n'y était pour rien.
"""
from __future__ import annotations

import pytest

PREFLIGHT = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


@pytest.mark.parametrize("origine", [
    "http://localhost:5173",
    # Le port que prend Vite quand un premier serveur occupe déjà 5173.
    "http://localhost:5174",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
])
async def test_le_preflight_accepte_toute_origine_locale(client_api, origine):
    reponse = await client_api.options(
        "/auth/login", headers={"Origin": origine, **PREFLIGHT}
    )

    assert reponse.status_code == 200, origine
    assert reponse.headers["access-control-allow-origin"] == origine


async def test_une_origine_etrangere_reste_refusee(client_api):
    """La tolérance vaut pour le poste local, pas pour n'importe quel site."""

    reponse = await client_api.options(
        "/auth/login",
        headers={"Origin": "http://echo-cnam.exemple.ci", **PREFLIGHT},
    )

    assert reponse.status_code == 400


@pytest.mark.parametrize("origine", [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
])
async def test_la_poignee_de_main_temps_reel_accepte_les_origines_locales(origine):
    """Le temps réel a son propre CORS, et il doit suivre celui du REST.

    Le handshake précède l'authentification : refusé, le client ne peut même
    pas présenter son jeton, et le bandeau reste sur « reconnexion » sans que
    rien n'explique pourquoi.
    """

    import httpx

    from api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://tests") as client:
        reponse = await client.get(
            "/socket.io/?EIO=4&transport=polling", headers={"Origin": origine}
        )

    assert reponse.status_code == 200
    assert reponse.headers.get("access-control-allow-origin") == origine


async def test_la_connexion_repond_bien_a_une_requete_avec_origine(client_api):
    """Le préflight passé, la requête réelle doit porter l'en-tête CORS."""

    reponse = await client_api.post(
        "/auth/login",
        json={"identifiant": "inconnu", "mot_de_passe": "peu importe"},
        headers={"Origin": "http://localhost:5174"},
    )

    assert reponse.status_code == 401
    assert reponse.headers["access-control-allow-origin"] == "http://localhost:5174"
