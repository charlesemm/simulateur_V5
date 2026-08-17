from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """Décrit une écriture métier observable produite par un passage."""

    event_type: str
    passage_id: str
    simulated_at: datetime
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'événement en dictionnaire sérialisable."""
        data = asdict(self)
        data["simulated_at"] = self.simulated_at.isoformat()
        return data


EventCallback = Callable[[SimulationEvent], Awaitable[None] | None]


async def default_event_callback(event: SimulationEvent) -> None:
    """Point d'extension neutre utilisé avant le branchement temps réel."""
    del event