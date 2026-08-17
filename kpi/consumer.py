"""Regroupe les événements et diffuse au plus un snapshot par seconde."""

from __future__ import annotations
import asyncio
import logging
from events import EventBus
from kpi.service import KpiService

logger = logging.getLogger(__name__)

class KpiConsumer:
    """Consomme le bus avec un debounce glissant d'une seconde."""

    def __init__(self, bus: EventBus, socket_server, debounce_seconds: float = 1.0) -> None:
        self.bus = bus
        self.socket_server = socket_server
        self.debounce_seconds = debounce_seconds
        self.service = KpiService()
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Démarre une seule boucle de consommation."""

        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Arrête la boucle sans laisser de tâche orpheline."""

        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        """Attend le premier message puis absorbe la rafale pendant une seconde."""

        queue = await self.bus.subscribe()
        try:
            while self._running:
                first = await queue.get()
                changed = {first.event_type}
                await asyncio.sleep(self.debounce_seconds)
                while not queue.empty():
                    changed.add(queue.get_nowait().event_type)
                snapshot = await self.service.calculate_snapshot()
                payload = {"changed": sorted(changed), "data": snapshot}
                await self.socket_server.emit("kpi:update", payload, namespace="/kpi")
                logger.info("Snapshot KPI diffusé après %s type(s) d'événement.", len(changed))
        finally:
            await self.bus.unsubscribe(queue)