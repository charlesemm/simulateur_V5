"""Vérifie que le navigateur peut joindre l'API depuis un poste de travail.

Un préflight refusé bloque la requête avant qu'elle parte : côté navigateur,
c'est indiscernable d'une API éteinte. Ce cas a coûté une soirée de recherche
sur un mot de passe qui n'y était pour rien.
"""
from __future__ import annotations

import pytest
import socketio

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


# ── Une seule règle pour les deux portes (AUDIT A04) ─────────────────────
#
# Socket.IO recevait « * » dès que CORS_ORIGIN_REGEX était posée — donc en
# production, où elle est obligatoire — pendant que le REST restait fermé.

async def _poignee_de_main(origine: str):
    import httpx

    from api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://tests") as client:
        return await client.get(
            "/socket.io/?EIO=4&transport=polling", headers={"Origin": origine}
        )


async def test_la_poignee_de_main_refuse_une_origine_etrangere():
    reponse = await _poignee_de_main("http://echo-cnam.exemple.ci")

    assert reponse.status_code == 400
    assert "access-control-allow-origin" not in reponse.headers


async def test_en_production_le_temps_reel_suit_le_domaine(monkeypatch):
    from app import cors

    monkeypatch.setattr(cors, "ORIGINES", ["https://echo.ipscnam.ci"])
    monkeypatch.setattr(cors, "MOTIF_ORIGINE", r"https://echo\.ipscnam\.ci")

    admise = await _poignee_de_main("https://echo.ipscnam.ci")
    assert admise.status_code == 200
    assert admise.headers["access-control-allow-origin"] == "https://echo.ipscnam.ci"

    for etrangere in ("https://attaquant.exemple", "http://localhost:5173",
                      "https://echo.ipscnam.ci.attaquant.exemple"):
        assert (await _poignee_de_main(etrangere)).status_code == 400, etrangere


# ── Le compte relu à la connexion temps réel (AUDIT A11) ─────────────────

async def _connecter(jeton: str) -> None:
    from realtime.socket_server import connect

    await connect("sid-de-test", {}, {"token": jeton})


async def _jeton_de(client_api, **compte) -> tuple[str, str, str]:
    creation = await client_api.post("/users", json={"role": "observateur", **compte})
    temporaire = creation.json()["mot_de_passe_temporaire"]
    connexion = await client_api.post("/auth/login", json={
        "identifiant": compte["nom_utilisateur"], "mot_de_passe": temporaire})
    return (connexion.json()["access_token"], temporaire,
            creation.json()["utilisateur"]["utilisateur_uuid"])


async def test_le_temps_reel_refuse_un_mot_de_passe_temporaire(client_api):
    jeton, _temporaire, _uuid = await _jeton_de(
        client_api, email="neuf@cnam.ci", nom_utilisateur="neuf", nom_complet="Neuf")

    with pytest.raises(socketio.exceptions.ConnectionRefusedError):
        await _connecter(jeton)


async def test_le_temps_reel_refuse_un_compte_desactive(client_api):
    jeton, temporaire, uuid_compte = await _jeton_de(
        client_api, email="eteint@cnam.ci", nom_utilisateur="eteint", nom_complet="Éteint")
    change = await client_api.post(
        "/auth/change-password", headers={"Authorization": f"Bearer {jeton}"},
        json={"mot_de_passe_actuel": temporaire, "nouveau_mot_de_passe": "MotDePasseChoisi1"})
    jeton_valide = change.json()["access_token"]

    await client_api.patch(f"/users/{uuid_compte}", json={"statut_actif": False})

    with pytest.raises(socketio.exceptions.ConnectionRefusedError):
        await _connecter(jeton_valide)


async def test_le_temps_reel_refuse_un_jeton_revoque(client_api):
    """Le jeton émis sous le mot de passe temporaire ne vaut plus après."""

    jeton, temporaire, _uuid = await _jeton_de(
        client_api, email="revoque@cnam.ci", nom_utilisateur="revoque", nom_complet="Révoqué")
    await client_api.post(
        "/auth/change-password", headers={"Authorization": f"Bearer {jeton}"},
        json={"mot_de_passe_actuel": temporaire, "nouveau_mot_de_passe": "MotDePasseChoisi1"})

    with pytest.raises(socketio.exceptions.ConnectionRefusedError):
        await _connecter(jeton)
