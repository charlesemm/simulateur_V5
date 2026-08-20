"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

import os

import socketio
from events import event_bus
from kpi import KpiConsumer, KpiService
from metrics.registry import registry as metrics_registry

# Mêmes origines que le middleware CORS de FastAPI (api/main.py), pour qu'une
# seule variable d'environnement pilote REST et temps réel.
_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
_cors_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_cors_origins)
socket_app = socketio.ASGIApp(sio)
kpi_consumer = KpiConsumer(event_bus, sio)

@sio.event(namespace="/kpi")
async def connect(sid, environ, auth) -> None:
    """Accepte le client et lui envoie immédiatement un état complet."""
    metrics_registry.enregistrer_connexion_socketio()
    del environ, auth
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
    """Démarre le consommateur ; FastAPI appellera cette fonction au lifespan."""

    await kpi_consumer.start()


async def shutdown_event_pipeline() -> None:
    """Arrête le consommateur lors de l'extinction ASGI."""

    await kpi_consumer.stop()

@sio.event(namespace="/kpi")
async def disconnect(sid) -> None:
    """Suit les déconnexions pour le rapport technique quotidien."""

    metrics_registry.enregistrer_deconnexion_socketio()