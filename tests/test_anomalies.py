"""Vérifie que l'injection d'anomalies n'agit que lorsqu'on la demande."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from anomalies.config import AnomaliesConfig

REFERENCE = Decimal("10000")
JOUR = date(2026, 8, 21)


def config(**options) -> AnomaliesConfig:
    """Fabrique une configuration déterministe pour les tests."""

    return AnomaliesConfig(seed=1234, **options)


def test_desactivee_rien_n_est_touche():
    anomalies = config(enabled=False, rate=1.0)
    assert anomalies.injecter_montant(REFERENCE) == REFERENCE
    assert anomalies.injecter_date(JOUR) == JOUR
    assert anomalies.injecter_quantite(1, 1) == 1
    assert anomalies.injected_count == 0


def test_taux_nul_rien_n_est_touche():
    """Activée mais à 0 %, la configuration doit rester sans effet."""

    anomalies = config(enabled=True, rate=0.0)
    for _ in range(200):
        assert anomalies.injecter_montant(REFERENCE) == REFERENCE
    assert anomalies.injected_count == 0


def test_le_taux_est_borne_entre_zero_et_un():
    assert config(rate=-5.0).rate == 0.0
    assert config(rate=42.0).rate == 1.0


def test_a_cent_pour_cent_le_montant_est_toujours_fausse():
    anomalies = config(enabled=True, rate=1.0)
    resultats = [anomalies.injecter_montant(REFERENCE) for _ in range(50)]
    assert all(valeur != REFERENCE for valeur in resultats)
    # Les deux formes attendues : négatif, ou démesuré.
    assert any(valeur < 0 for valeur in resultats)
    assert any(valeur > REFERENCE for valeur in resultats)
    assert anomalies.injected_count == 50


def test_la_date_faussee_est_antidatee_d_au_plus_un_an():
    anomalies = config(enabled=True, rate=1.0)
    for _ in range(100):
        faussee = anomalies.injecter_date(JOUR)
        assert faussee < JOUR
        assert (JOUR - faussee).days <= 365


def test_la_quantite_servie_depasse_la_quantite_prescrite():
    anomalies = config(enabled=True, rate=1.0)
    for _ in range(100):
        assert anomalies.injecter_quantite(2, 2) > 2


def test_le_compteur_suit_le_nombre_reel_d_injections():
    anomalies = config(enabled=True, rate=1.0)
    for _ in range(7):
        anomalies.injecter_montant(REFERENCE)
    for _ in range(3):
        anomalies.injecter_date(JOUR)
    assert anomalies.injected_count == 10
