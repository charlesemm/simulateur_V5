"""Expose les métriques d'observabilité et de performance système du simulateur."""
from __future__ import annotations

from fastapi import APIRouter
from metrics.registry import registry as metrics_registry
from api.services.simulation_manager import simulation_manager

router = APIRouter(prefix="/metrics", tags=["Métriques Techniques"])


@router.get("/technical")
async def get_technical_metrics() -> dict:
    """Retourne l'ensemble des métriques d'observabilité, de charge et de performance."""
    snapshot = metrics_registry.snapshot()
    status = simulation_manager.status()
    snapshot["moteur_etat"] = status["etat"]
    snapshot["moteur_vitesse"] = status["vitesse"]
    snapshot["passages_actifs"] = status["passages_actifs"]
    snapshot["passages_simultanes_max"] = status["passages_simultanes_max"]
    return snapshot


@router.post("/technical/reset")
async def reset_technical_metrics() -> dict[str, str]:
    """Réinitialise les compteurs de métriques techniques."""
    metrics_registry.passages_reussis = 0
    metrics_registry.passages_echoues = 0
    metrics_registry.pic_passages_simultanes = 0
    metrics_registry.evenements_totaux = 0
    metrics_registry.recalculs_kpi = 0
    metrics_registry.duree_totale_recalculs_kpi_secondes = 0.0
    metrics_registry.requetes_api_total = 0
    metrics_registry.duree_totale_requetes_api_secondes = 0.0
    return {"message": "Métriques techniques réinitialisées."}
