"""Configuration et injecteurs d'anomalies « douces ».

Les anomalies douces sont des données incohérentes qui respectent les
contraintes SQL mais révèlent les bugs métier : montants négatifs, dates
antidatées, quantités servies supérieures aux quantités prescrites.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Any


class AnomaliesConfig:
    """Configuration en mémoire, pilotée par l'API et persistée en base."""

    def __init__(
        self,
        enabled: bool = False,
        rate: float = 0.0,
        seed: int = 42,
        severity: str = "soft",
    ) -> None:
        self.enabled = enabled
        self.rate = max(0.0, min(1.0, rate))
        self.random = random.Random(seed)
        self.severity = severity
        self.injected_count = 0

    def should_inject(self) -> bool:
        """Décide aléatoirement s'il faut injecter une anomalie."""
        if not self.enabled:
            return False
        return self.random.random() < self.rate

    def record_injection(self) -> None:
        """Incrémente le compteur affiché par le dashboard."""
        self.injected_count += 1

    # ── Injecteurs utilisés par le moteur de simulation ──────────────────

    def injecter_montant(self, montant: Decimal) -> Decimal:
        """Retourne un montant négatif ou démesuré, ou la valeur d'origine."""
        if not self.should_inject():
            return montant
        self.record_injection()
        if self.random.random() < 0.5:
            return Decimal("-1000.00")
        return Decimal("999999999.99")

    def injecter_date(self, valeur: date) -> date:
        """Retourne une date antidatée jusqu'à un an, ou la valeur d'origine."""
        if not self.should_inject():
            return valeur
        self.record_injection()
        return valeur - timedelta(days=self.random.randint(1, 365))

    def injecter_quantite(self, prescrite: int, servie: int) -> int:
        """Retourne une quantité servie supérieure à la quantité prescrite."""
        if not self.should_inject():
            return servie
        self.record_injection()
        return prescrite + self.random.randint(1, 20)

    # ── Injecteurs utilisés par le seed ──────────────────────────────────

    def injecter_numero_secu(self, numero: str) -> str:
        """Retourne un numéro de sécurité sociale manifestement invalide."""
        if not self.should_inject():
            return numero
        self.record_injection()
        return "00000000000000"

    def injecter_email(self, email: str) -> str:
        """Retourne une adresse électronique invalide."""
        if not self.should_inject():
            return email
        self.record_injection()
        return "pas_un_email_valide"


# Instance unique partagée par tout le processus (seed, moteur, API).
anomalies_config = AnomaliesConfig()


def apply_anomalies_to_row(
    row: dict[str, Any], config: AnomaliesConfig, row_type: str
) -> dict[str, Any]:
    """Applique les anomalies à une ligne du seed selon son type."""
    if not config.enabled:
        return row

    if row_type == "agent" and "agent_email" in row:
        row["agent_email"] = config.injecter_email(row["agent_email"])
    elif row_type == "insured" and "numero_secu" in row:
        row["numero_secu"] = config.injecter_numero_secu(row["numero_secu"])

    return row
