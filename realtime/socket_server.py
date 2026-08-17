"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

import socketio
from events import event_bus
from kpi import KpiConsumer, KpiService

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])
socket_app = socketio.ASGIApp(sio)
kpi_consumer = KpiConsumer(event_bus, sio)

@sio.event(namespace="/kpi")
async def connect(sid, environ, auth) -> None:
    """Accepte le client et lui envoie immédiatement un état complet."""

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