from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """Décrit une écriture métier observable produite par un passage."""

    event_type: str
    passage_id: str
    simulated_at: datetime
    payload: dict[str, Any]
    # Exécution qui a produit l'événement, nulle hors d'un run enregistré.
    simulation_id: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'événement en dictionnaire sérialisable."""
        data = asdict(self)
        data["simulated_at"] = self.simulated_at.isoformat()
        # L'identifiant d'exécution est un UUID : il ne survivrait pas tel quel
        # à une sérialisation JSON.
        data["simulation_id"] = str(self.simulation_id) if self.simulation_id else None
        return data


EventCallback = Callable[[SimulationEvent], Awaitable[None] | None]


async def default_event_callback(event: SimulationEvent) -> None:
    """Point d'extension neutre utilisé avant le branchement temps réel."""
    del event