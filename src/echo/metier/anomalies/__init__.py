"""Injection contrôlée de données atypiques, pour éprouver la robustesse."""

from echo.metier.anomalies.catalogue import CATALOGUE_INITIAL, CODES, TypeAnomalie
from echo.metier.anomalies.config import (
    AnomaliesConfig, ContexteInjection, Injection, anomalies_config,
    apply_anomalies_to_row,
)
from echo.metier.anomalies.models import AnomaliesConfigRow, AnomalyInjection, AnomalyType

__all__ = [
    "AnomaliesConfig",
    "AnomaliesConfigRow",
    "AnomalyInjection",
    "AnomalyType",
    "CATALOGUE_INITIAL",
    "CODES",
    "ContexteInjection",
    "Injection",
    "TypeAnomalie",
    "anomalies_config",
    "apply_anomalies_to_row",
]
