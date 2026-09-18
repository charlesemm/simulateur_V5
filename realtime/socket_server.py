"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

import socketio
from app import cors
from app.database import async_session_factory
from auth.dependencies import JetonRefuse, utilisateur_du_jeton
from events import event_bus
from kpi import KpiConsumer, KpiService
from metrics.registry import registry as metrics_registry
from realtime.parcours_consumer import ParcoursConsumer

# Même règle que le REST, par la même fonction : Socket.IO ne lit pas
# d'expression régulière, mais il accepte une fonction qui juge l'origine.
# Une liste seule rejouerait la panne du 23 août (Vite sur un autre port,
# poignée de main refusée, bandeau bloqué sur « reconnexion ») ; « * » ouvrait
# le temps réel à toute origine dès que le motif était posé, production
# comprise.
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors.origine_autorisee)
socket_app = socketio.ASGIApp(sio)
kpi_consumer = KpiConsumer(event_bus, sio)
# Deux consommateurs, deux abonnements distincts au bus : chacun a sa file, et
# l'agrégation des KPI ne retient pas la diffusion du parcours.
parcours_consumer = ParcoursConsumer(event_bus, sio)

@sio.event(namespace="/kpi")
async def connect(sid, environ, auth) -> None:
    """Vérifie le jeton JWT du client avant de lui ouvrir le flux KPI.

    Le CORS ne protège que le navigateur : sans ce contrôle, n'importe quel
    client Socket.IO recevrait le snapshot complet et toutes les diffusions.
    La signature ne suffit pas : le compte est relu comme pour le REST — un
    compte désactivé, ou dont le mot de passe a changé, est refusé, tout
    comme un compte encore sous mot de passe temporaire, à qui le REST
    n'ouvre que le changement de mot de passe.
    """

    del environ
    jeton = (auth or {}).get("token")
    if not jeton:
        raise socketio.exceptions.ConnectionRefusedError(
            "Jeton d'authentification absent."
        )
    try:
        async with async_session_factory() as session:
            utilisateur = await utilisateur_du_jeton(jeton, session)
    except JetonRefuse as refus:
        raise socketio.exceptions.ConnectionRefusedError(str(refus)) from refus
    if utilisateur.doit_changer_mot_de_passe:
        raise socketio.exceptions.ConnectionRefusedError(
            "Changez votre mot de passe temporaire avant de continuer."
        )

    metrics_registry.enregistrer_connexion_socketio()
    snapshot = await KpiService().calculate_snapshot()
    await sio.emit("kpi:snapshot", snapshot, to=sid, namespace="/kpi")

@sio.on("kpi:subscribe", namespace="/kpi")
async def subscribe_center(sid, data) -> dict:
    """Inscrit le client dans la room d'un centre pour les extensions futures."""

    center_code = str(data.get("centre_sante_code", "")).strip()
    if not center_code:
        return {"ok": False, "erreur": "Le code centre est obligatoire."}
    await sio.enter_room(sid, f"centre:{center_code}", namespace="/kpi")
    return {"ok": True, "room": f"centre:{center_code}"}


async def startup_event_pipeline() -> None:
    """Démarre les consommateurs ; FastAPI appelle cette fonction au lifespan."""

    await kpi_consumer.start()
    await parcours_consumer.start()


async def shutdown_event_pipeline() -> None:
    """Arrête les consommateurs lors de l'extinction ASGI."""

    await kpi_consumer.stop()
    await parcours_consumer.stop()

@sio.event(namespace="/kpi")
async def disconnect(sid) -> None:
    """Suit les déconnexions pour le rapport technique quotidien."""

    metrics_registry.enregistrer_deconnexion_socketio()