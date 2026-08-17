from __future__ import annotations

import asyncio
import logging
import random
from uuid import UUID

from sqlalchemy import select
from app.database import async_session_factory
from app.models import InsuredPerson
from simulation.events import EventCallback, default_event_callback
from simulation.passage import PassageSimulation
from simulation_config import DEFAULT_CONFIG, SimulationConfig

logger = logging.getLogger(__name__)

class SimulationEngine:
    """Pilote les tâches et interdit deux passages simultanés par assuré."""

    def __init__(self, config: SimulationConfig = DEFAULT_CONFIG,
                 event_callback: EventCallback = default_event_callback) -> None:
        self.config = config
        self.event_callback = event_callback
        self._speed = config.default_speed
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._insured_in_progress: set[UUID] = set()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(config.max_concurrent_passages)
        self._random = random.Random(config.random_seed)

    def set_speed(self, speed: float) -> None:
        """Change immédiatement le rapport temps simulé / temps réel."""
        if speed <= 0:
            raise ValueError("La vitesse doit être strictly positive.")
        self._speed = speed

    async def _reserve_insured(self) -> UUID:
        """Réserve atomiquement un assuré qui n'est pas déjà en parcours."""
        async with self._lock:
            async with async_session_factory() as session:
                ids = list((await session.execute(select(InsuredPerson.personne_uuid))).scalars())
            available = [insured_id for insured_id in ids if insured_id not in self._insured_in_progress]
            if not available:
                raise RuntimeError("Aucun assuré disponible pour un nouveau passage.")
            insured_id = self._random.choice(available)
            self._insured_in_progress.add(insured_id)
            return insured_id

    async def _run_one(self, insured_id: UUID, sequence: int) -> None:
        """Exécute un passage sous limite de concurrence puis libère l'assuré."""
        try:
            async with self._semaphore:
                await PassageSimulation(
                    insured_id, self.config, lambda: self._speed,
                    self.event_callback, self.config.random_seed + sequence,
                ).run()
        except Exception:
            logger.exception("Le passage %s a échoué.", sequence)
        finally:
            async with self._lock:
                self._insured_in_progress.discard(insured_id)

    async def start(self, number_of_passages: int | None = None) -> None:
        """Crée un flux fini ou continu de tâches de passage."""
        self._running = True
        sequence = 0
        while self._running and (number_of_passages is None or sequence < number_of_passages):
            insured_id = await self._reserve_insured()
            sequence += 1
            task = asyncio.create_task(self._run_one(insured_id, sequence))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            if number_of_passages is None or sequence < number_of_passages:
                delay = self._random.expovariate(1 / self.config.passage_arrival_mean_seconds)
                await asyncio.sleep(delay / self._speed)
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks))
        self._running = False

    async def stop(self) -> None:
        """Arrête la création et annule proprement les tâches restantes."""
        self._running = False
        for task in tuple(self._tasks):
            task.cancel()
        await asyncio.gather(*tuple(self._tasks), return_exceptions=True)