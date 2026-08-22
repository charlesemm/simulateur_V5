"""Gère l'unique instance du moteur utilisée par les endpoints FastAPI."""

from __future__ import annotations
import asyncio
from dataclasses import replace
from uuid import UUID
from events import publish_simulation_event
from simulation import SimulationEngine
from simulation.models import STATUT_ARRETEE, STATUT_ECHOUEE
from simulation.runs import cloturer_execution, ouvrir_execution
from simulation_config import DEFAULT_CONFIG

class SimulationManager:
    """Sérialise les commandes start/stop et conserve la tâche principale."""

    def __init__(self) -> None:
        self._engine: SimulationEngine | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._maximum = DEFAULT_CONFIG.max_concurrent_passages
        self._simulation_id: UUID | None = None

    async def start(self, speed: float, maximum: int,
                    utilisateur_uuid: UUID | None = None) -> None:
        """Ouvre une exécution et démarre un flux continu.

        Refuse un double démarrage : une seule exécution est ouverte à la fois,
        sans quoi deux moteurs se disputeraient les mêmes assurés.
        """

        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("Le simulateur est déjà démarré.")
            config = replace(DEFAULT_CONFIG, default_speed=speed, max_concurrent_passages=maximum)
            self._simulation_id = await ouvrir_execution(
                {
                    "vitesse": speed,
                    "passages_simultanes_max": maximum,
                    "graine": config.random_seed,
                },
                utilisateur_uuid,
            )
            self._engine = SimulationEngine(config, publish_simulation_event, self._simulation_id)
            self._engine.set_speed(speed)
            self._maximum = maximum
            self._task = asyncio.create_task(self._engine.start())

    async def stop(self) -> None:
        """Arrête le moteur, attend sa tâche puis clôture l'exécution."""

        async with self._lock:
            if self._engine:
                await self._engine.stop()
            resultats = []
            if self._task:
                resultats = await asyncio.gather(self._task, return_exceptions=True)
            if self._simulation_id and self._engine:
                # Une exception remontée par la tâche principale signe une
                # exécution interrompue, pas un arrêt demandé : l'annulation
                # provoquée par stop() n'en est pas une.
                echec = any(
                    isinstance(resultat, BaseException)
                    and not isinstance(resultat, asyncio.CancelledError)
                    for resultat in resultats
                )
                await cloturer_execution(
                    self._simulation_id, STATUT_ECHOUEE if echec else STATUT_ARRETEE,
                    self._engine.passages_reussis, self._engine.passages_echoues,
                )
            self._simulation_id = None
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
            "simulation_id": self._simulation_id,
            "vitesse": self._engine._speed if self._engine else DEFAULT_CONFIG.default_speed,
            "passages_actifs": len(self._engine._insured_in_progress) if self._engine else 0,
            "passages_simultanes_max": self._maximum,
        }
simulation_manager = SimulationManager()
