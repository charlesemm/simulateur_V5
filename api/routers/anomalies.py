"""Gestion de la configuration des anomalies du simulateur."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import require_role
from seed.anomalies import anomalies_config

router = APIRouter(
    prefix="/anomalies",
    tags=["anomalies"],
    dependencies=[Depends(require_role("administrateur"))],
)


class AnomaliesConfigRequest(BaseModel):
    """Requête pour modifier la configuration."""
    enabled: bool | None = None
    rate: float | None = Field(None, ge=0.0, le=1.0)
    severity: str | None = None


class AnomaliesConfigResponse(BaseModel):
    """Réponse avec la configuration actuelle."""
    enabled: bool
    rate: float
    severity: str
    injected_count: int


@router.get("", response_model=AnomaliesConfigResponse)
async def get_anomalies_config() -> AnomaliesConfigResponse:
    """Retourne la configuration courante des anomalies."""
    return AnomaliesConfigResponse(
        enabled=anomalies_config.enabled,
        rate=anomalies_config.rate,
        severity=anomalies_config.severity,
        injected_count=anomalies_config.injected_count,
    )


@router.patch("", response_model=AnomaliesConfigResponse)
async def update_anomalies_config(payload: AnomaliesConfigRequest) -> AnomaliesConfigResponse:
    """Modifie la configuration à la volée (en mémoire uniquement pour v1)."""
    if payload.enabled is not None:
        anomalies_config.enabled = payload.enabled
    if payload.rate is not None:
        anomalies_config.rate = payload.rate
    if payload.severity is not None:
        anomalies_config.severity = payload.severity

    return AnomaliesConfigResponse(
        enabled=anomalies_config.enabled,
        rate=anomalies_config.rate,
        severity=anomalies_config.severity,
        injected_count=anomalies_config.injected_count,
    )


@router.post("/reset")
async def reset_anomalies_count() -> dict[str, str]:
    """Réinitialise le compteur d'anomalies injectées."""
    anomalies_config.injected_count = 0
    return {"message": "Compteur d'anomalies réinitialisé."}