"""Expose le snapshot et les séries historiques de KPI."""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from api.schema import Granularity, KpiHistoryResponse, KpiName, KpiSnapshotResponse
from api.services.history import calculate_history
from kpi import KpiService

router = APIRouter(prefix="/kpi", tags=["KPI"])

@router.get("/snapshot", response_model=KpiSnapshotResponse)
async def get_snapshot() -> KpiSnapshotResponse:
    """Retourne le même snapshot que l'événement Socket.IO initial."""

    return KpiSnapshotResponse.model_validate(await KpiService().calculate_snapshot())

@router.get("/{kpi_name}/history", response_model=KpiHistoryResponse)
async def get_history(
    kpi_name: KpiName,
    since: datetime = Query(default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=24)),
    granularite: Granularity = Granularity.heure,
) -> KpiHistoryResponse:
    """Retourne une série ordonnée pour une courbe du dashboard."""

    points = await calculate_history(kpi_name, since, granularite)
    return KpiHistoryResponse(kpi_name=kpi_name, granularite=granularite, since=since, points=points)

