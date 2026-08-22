from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4
from app.database import async_session_factory
from events.models import EventJournal

@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Format interne indépendant de Socket.IO et du moteur."""

    event_type: str
    passage_id: str
    simulated_at: datetime
    payload: dict[str, Any]
    # Exécution qui a produit l'événement, nulle hors d'un run enregistré.
    simulation_id: Any = None

class EventBus:
    """Copie chaque événement dans la file de chaque abonné actif."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[DomainEvent]:
        """Crée une file privée afin qu'aucun abonné ne vole un message."""

        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=5000)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[DomainEvent]) -> None:
        """Retire proprement la file d'un consommateur arrêté."""

        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: DomainEvent) -> None:
        """Journalise avant de publier, garantissant un KPI reconstructible."""

        async with async_session_factory() as session:
            session.add(EventJournal(
                evenement_id=uuid4(), type_evenement=event.event_type,
                passage_id=event.passage_id, simulated_at=event.simulated_at,
                payload=event.payload, simulation_id=event.simulation_id,
                utilisateur_id_creation="event_bus",
            ))
            await session.commit()
        async with self._lock:
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            await queue.put(event)

event_bus = EventBus()

async def publish_simulation_event(event) -> None:
    """Adapte directement le callback SimulationEvent de l'étape 3."""

    await event_bus.publish(DomainEvent(
        event_type=event.event_type, passage_id=event.passage_id,
        simulated_at=event.simulated_at, payload=event.payload,
        simulation_id=event.simulation_id,
    ))



