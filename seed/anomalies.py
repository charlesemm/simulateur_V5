"""Injecteur d'anomalies 'douces' pour le seed du simulateur.

Les anomalies 'douces' sont des données bizarres ou incohérentes qui
respectent les contraintes SQL mais qui révèlent des bugs métier.
"""
from __future__ import annotations

import random
from decimal import Decimal
from datetime import date, timedelta
from typing import Any, TypeVar

T = TypeVar("T")


class AnomaliesConfig:
    """Configuration en mémoire, chargeable depuis env ou modifiable via API."""

    def __init__(
            self,
            enabled: bool = False,
            rate: float = 0.0,  # Probabilité d'injection (0.0 à 1.0)
            seed: int = 42,
            severity: str = "soft",  # "soft" v1 ou "hard" v2
    ) -> None:
        self.enabled = enabled
        self.rate = max(0.0, min(1.0, rate))  # Clamp à [0, 1]
        self.random = random.Random(seed)
        self.severity = severity
        self.injected_count = 0

    def should_inject(self) -> bool:
        """Décide aléatoirement s'il faut injecter une anomalie."""
        if not self.enabled:
            return False
        return self.random.random() < self.rate

    def record_injection(self) -> None:
        """Enregistre une anomalie injectée (pour le rapport)."""
        self.injected_count += 1


# Instance unique, partagée par tout le processus.
anomalies_config = AnomaliesConfig()


def inject_numero_secu(numero: str, config: AnomaliesConfig) -> str:
    """Retourne un NUMERO_SECU potentiellement malformé."""
    if config.should_inject():
        config.record_injection()
        return "00000000000000"
    return numero


def inject_email(email: str, config: AnomaliesConfig) -> str:
    """Retourne un email potentiellement invalide."""
    if config.should_inject():
        config.record_injection()
        return "pas_un_email_valide"
    return email


def inject_date_cohesion(start: date, end: date | None, config: AnomaliesConfig) -> date | None:
    """Retourne une date de fin potentiellement avant la date de début."""
    if not end or not config.should_inject():
        return end
    config.record_injection()
    return start - timedelta(days=config.random.randint(1, 365))


def inject_montant(montant: Decimal, config: AnomaliesConfig) -> Decimal:
    """Retourne un montant potentiellement aberrant."""
    if config.should_inject():
        config.record_injection()
        choice = config.random.choice(["negatif", "extreme"])
        if choice == "negatif":
            return Decimal("-1000.00")
        else:
            return Decimal("999999999.99")
    return montant


def apply_anomalies_to_row(row: dict[str, Any], config: AnomaliesConfig, row_type: str) -> dict[str, Any]:
    """Applique des anomalies à une ligne selon son type.

    row_type : "agent", "insured", "center_assignment"
    """
    if not config.enabled:
        return row

    if row_type == "agent":
        if "agent_email" in row:
            row["agent_email"] = inject_email(row["agent_email"], config)
    elif row_type == "insured":
        if "numero_secu" in row:
            row["numero_secu"] = inject_numero_secu(row["numero_secu"], config)
    elif row_type == "center_assignment":
        if "date_fin" in row and "date_debut" in row:
            row["date_fin"] = inject_date_cohesion(row["date_debut"], row["date_fin"], config)

    return row