"""Charge et sauvegarde la configuration des anomalies en base."""
from __future__ import annotations

import logging
from decimal import Decimal

from anomalies.config import anomalies_config
from anomalies.models import AnomaliesConfigRow
from app.database import async_session_factory

logger = logging.getLogger(__name__)

# La table ne contient qu'une seule ligne, identifiée par cette clé.
CONFIG_ID = 1


async def charger_configuration() -> None:
    """Restaure la configuration persistée dans l'instance en mémoire."""

    async with async_session_factory() as session:
        ligne = await session.get(AnomaliesConfigRow, CONFIG_ID)
        if ligne is None:
            logger.info(
                "Aucune configuration d'anomalies en base : valeurs par défaut."
            )
            return
        anomalies_config.enabled = ligne.enabled
        anomalies_config.rate = float(ligne.rate)
        anomalies_config.severity = ligne.severity
        anomalies_config.injected_count = ligne.injected_count
    logger.info(
        "Configuration d'anomalies restaurée (activee=%s, taux=%s, injectees=%s).",
        anomalies_config.enabled,
        anomalies_config.rate,
        anomalies_config.injected_count,
    )


async def sauvegarder_configuration() -> None:
    """Écrit l'état courant de l'instance en mémoire dans la base."""

    async with async_session_factory() as session:
        ligne = await session.get(AnomaliesConfigRow, CONFIG_ID)
        if ligne is None:
            ligne = AnomaliesConfigRow(config_id=CONFIG_ID)
            session.add(ligne)
        ligne.enabled = anomalies_config.enabled
        ligne.rate = Decimal(str(round(anomalies_config.rate, 2)))
        ligne.severity = anomalies_config.severity
        ligne.injected_count = anomalies_config.injected_count
        await session.commit()
