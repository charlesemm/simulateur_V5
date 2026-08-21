"""Injection contrôlée de données atypiques, pour éprouver la robustesse."""

from anomalies.config import AnomaliesConfig, anomalies_config, apply_anomalies_to_row
from anomalies.models import AnomaliesConfigRow

__all__ = [
    "AnomaliesConfig",
    "AnomaliesConfigRow",
    "anomalies_config",
    "apply_anomalies_to_row",
]
