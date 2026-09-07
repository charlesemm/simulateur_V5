"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

import jwt
import socketio
from app import cors
from auth.security import decode_access_token
from events import event_bus
from kpi import KpiConsumer, KpiService
from metrics.registry import registry as metrics_registry
from realtime.parcours_consumer import ParcoursConsumer

# FastAPI accepte toute origine locale par expression régulière ; Socket.IO ne
# sait pas lire d'expression régulière, seulement une liste ou « tout ».
# Laisser la seule liste explicite ici rejouerait exactement la panne du
# 23 août : le REST passait, la poignée de main du temps réel était refusée, et
# le bandeau restait bloqué sur « reconnexion » sans que rien ne l'explique.
#
# Ouvrir le temps réel ne rouvre pas les données : le gestionnaire connect
# ci-dessous exige un jeton JWT valide avant de diffuser quoi que ce soit.
# Vider CORS_ORIGIN_REGEX referme les deux d'un coup, pour un déploiement.
_cors_socketio = "*" if cors.MOTIF_ORIGINE else cors.ORIGINES

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_cors_socketio)
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
    """

    del environ
    jeton = (auth or {}).get("token")
    if not jeton:
        raise socketio.exceptions.ConnectionRefusedError(
            "Jeton d'authentification absent."
        )
    try:
        decode_access_token(jeton)
    except jwt.PyJWTError as exc:
        raise socketio.exceptions.ConnectionRefusedError(
            "Jeton invalide ou expiré."
        ) from exc

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