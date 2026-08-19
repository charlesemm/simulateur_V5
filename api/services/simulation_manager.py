"""Gère l'unique instance du moteur utilisée par les endpoints FastAPI."""

from __future__ import annotations
import asyncio
from dataclasses import replace
from events import publish_simulation_event
from simulation import SimulationEngine
from simulation_config import DEFAULT_CONFIG

class SimulationManager:
    """Sérialise les commandes start/stop et conserve la tâche principale."""

    def __init__(self) -> None:
        self._engine: SimulationEngine | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._maximum = DEFAULT_CONFIG.max_concurrent_passages

    async def start(self, speed: float, maximum: int) -> None:
        """Démarre un flux continu ou refuse un double démarrage."""

        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("Le simulateur est déjà démarré.")
            config = replace(DEFAULT_CONFIG, default_speed=speed, max_concurrent_passages=maximum)
            self._engine = SimulationEngine(config, publish_simulation_event)
            self._engine.set_speed(speed)
            self._maximum = maximum
            self._task = asyncio.create_task(self._engine.start())

    async def stop(self) -> None:
        """Arrête le moteur et attend la fin de sa tâche principale."""

        async with self._lock:
            if self._engine:
                await self._engine.stop()
            if self._task:
                await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
            self._engine = None

    def set_speed(self, speed: float) -> None:
        """Ajuste la vitesse ou signale que le moteur est arrêté."""

        if self._engine is None or not self._engine._running:
            raise RuntimeError("Le simulateur est arrêté.")
        self._engine.set_speed(speed)

    def status(self) -> dict:
        """Construit l'état courant consommé par le schéma Pydantic."""

        running = bool(self._engine and self._engine._running)
        return {
            "etat": "en_cours" if running else "arrete",
            "vitesse": self._engine._speed if self._engine else DEFAULT_CONFIG.default_speed,
            "passages_actifs": len(self._engine._insured_in_progress) if self._engine else 0,
            "passages_simultanes_max": self._maximum,
        }
simulation_manager = SimulationManager()
