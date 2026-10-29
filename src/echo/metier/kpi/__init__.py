"""Expose le calculateur et le consommateur KPI."""

from echo.metier.kpi.consumer import KpiConsumer
from echo.metier.kpi.service import KpiService

__all__ = ["KpiConsumer", "KpiService"]