"""Regroupe les routers HTTP du simulateur."""

from api.routers import centres, factures, kpi, simulation
from api.schema import HealthResponse

__all__ = ["centres", "factures", "kpi", "simulation"]