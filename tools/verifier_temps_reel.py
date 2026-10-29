import asyncio
from datetime import datetime, timezone
import socketio
import uvicorn
from events import DomainEvent, event_bus
from realtime import shutdown_event_pipeline, socket_app, startup_event_pipeline

async def main() -> None:
    """Lance ASGI, connecte un client et exige les deux événements KPI."""

    configuration = uvicorn.Config(socket_app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(configuration)
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    await startup_event_pipeline()

    client = socketio.AsyncClient()
    received = {"snapshot": asyncio.Event(), "update": asyncio.Event()}

    @client.on("kpi:snapshot", namespace="/kpi")
    async def on_snapshot(payload) -> None:
        print("SNAPSHOT", payload)
        received["snapshot"].set()

    @client.on("kpi:update", namespace="/kpi")
    async def on_update(payload) -> None:
        print("UPDATE", payload)
        received["update"].set()

    try:
        await client.connect("http://127.0.0.1:8765", namespaces=["/kpi"])
        await asyncio.wait_for(received["snapshot"].wait(), timeout=5)
        await event_bus.publish(DomainEvent(
            event_type="test.broadcast", passage_id="test-etape-4",
            simulated_at=datetime.now(timezone.utc), payload={"source": "test"},
        ))
        await asyncio.wait_for(received["update"].wait(), timeout=5)
        print("TEST RÉUSSI : snapshot et broadcast reçus.")
    finally:
        await client.disconnect()
        await shutdown_event_pipeline()
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(main())