"""Diffuse les événements de parcours au fil de leur production.

Jusqu'ici le bus n'alimentait que le calcul des KPI : les événements étaient
journalisés et agrégés, mais jamais montrés tels quels. Le terminal du
dashboard fabriquait donc ses lignes à partir des écarts entre deux relevés de
métriques — des messages plausibles, mais inventés.

Ce consommateur diffuse les vrais. Il regroupe par paquets courts et plafonne
leur taille : à vitesse ×3600 avec cent passages en parallèle, un envoi par
événement noierait le navigateur.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from events import EventBus

logger = logging.getLogger(__name__)

# Fenêtre de regroupement et plafond par envoi. Au-delà, seul le nombre
# d'événements écartés est transmis : un terminal ne se lit pas à 500 lignes
# par seconde, et le journal en base garde tout de toute façon.
FENETRE_SECONDES = 0.25
PLAFOND_PAR_ENVOI = 40


class ParcoursConsumer:
    """Relaie les événements du bus vers le namespace temps réel."""

    def __init__(self, bus: EventBus, socket_server,
                 fenetre_secondes: float = FENETRE_SECONDES,
                 plafond: int = PLAFOND_PAR_ENVOI) -> None:
        self.bus = bus
        self.socket_server = socket_server
        self.fenetre_secondes = fenetre_secondes
        self.plafond = plafond
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Démarre une seule boucle de relais."""

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

    @staticmethod
    def _serialiser(evenement) -> dict[str, Any]:
        """Met l'événement en forme pour le navigateur."""

        return {
            "type": evenement.event_type,
            "passage_id": evenement.passage_id,
            "simulation_id": (
                str(evenement.simulation_id) if evenement.simulation_id else None
            ),
            "simulated_at": evenement.simulated_at.isoformat(),
            "payload": evenement.payload,
        }

    async def _run(self) -> None:
        """Attend un événement, absorbe la rafale, puis diffuse le paquet."""

        queue = await self.bus.subscribe()
        try:
            while self._running:
                premier = await queue.get()
                paquet = [self._serialiser(premier)]
                await asyncio.sleep(self.fenetre_secondes)

                ecartes = 0
                while not queue.empty():
                    suivant = queue.get_nowait()
                    if len(paquet) < self.plafond:
                        paquet.append(self._serialiser(suivant))
                    else:
                        ecartes += 1

                await self.socket_server.emit(
                    "parcours:evenements",
                    {"evenements": paquet, "ecartes": ecartes},
                    namespace="/kpi",
                )
        finally:
            await self.bus.unsubscribe(queue)
