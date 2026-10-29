"""Regroupe les routers HTTP du simulateur."""

from echo.web.api.routers import centres, factures, kpi, parcours, simulation

__all__ = ["centres", "factures", "kpi", "parcours", "simulation"]