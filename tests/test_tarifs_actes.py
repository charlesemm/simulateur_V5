"""Montants facturés : autour du tarif de l'acte, jamais un montant unique.

Demande du 11/09/2026 : chaque prestation valait 10 000 FCFA, quel que soit
l'acte. Le montant suit désormais le tarif de référence, avec une large
variation — une consultation peut coûter 500 FCFA.
"""
from __future__ import annotations

import random
import statistics
from decimal import Decimal

from seed.constants import MEDICAL_ACTS
from seed.runner import build_medical_acts
from simulation.passage import (
    TARIFS_ACTES, VARIATION_MAX, VARIATION_MIN, montant_autour,
)

CONSULTATION = TARIFS_ACTES["CONS-GEN"]


def _tirages(tarif: Decimal, nombre: int = 5_000) -> list[Decimal]:
    tirage = random.Random(11)
    return [montant_autour(tarif, tirage) for _ in range(nombre)]


def test_chaque_acte_du_referentiel_porte_son_tarif():
    actes = build_medical_acts()
    assert len(actes) == len(MEDICAL_ACTS)
    for acte in actes:
        assert acte["acte_medical_tarif"] == TARIFS_ACTES[acte["acte_medical_code"]]
        assert acte["acte_medical_tarif"] > 0


def test_le_montant_reste_dans_la_fourchette_et_arrondi_a_50():
    for code in ("CONS-GEN", "DENT-EXT", "IMG-IRM", "HOS-REA"):
        tarif = TARIFS_ACTES[code]
        for montant in _tirages(tarif, 2_000):
            assert tarif * Decimal(str(VARIATION_MIN)) - 50 <= montant
            assert montant <= tarif * Decimal(str(VARIATION_MAX)) + 50
            assert montant % 50 == 0 and montant >= 50


def test_une_consultation_peut_descendre_vers_500():
    montants = _tirages(CONSULTATION)
    assert min(montants) <= 1_000
    assert max(montants) >= 8_000


def test_la_plupart_des_montants_restent_proches_du_tarif():
    """Des extrêmes possibles, mais pas une distribution plate."""

    montants = _tirages(CONSULTATION)
    assert abs(statistics.median(montants) - CONSULTATION) <= CONSULTATION * Decimal("0.2")
    assert len(set(montants)) > 50


def test_deux_actes_differents_ne_coutent_pas_pareil():
    assert statistics.median(_tirages(TARIFS_ACTES["IMG-IRM"], 500)) > \
        statistics.median(_tirages(TARIFS_ACTES["BIO-GLY"], 500)) * 10
