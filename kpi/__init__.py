"""Expose le calculateur et le consommateur KPI."""

from kpi.consumer import KpiConsumer
from kpi.service import KpiService

__all__ = ["KpiConsumer", "KpiService"]