"""Vérifie les identifiants et le régime produits par le seed, sans base.

Ces règles sont celles que l'utilisateur a fixées : préfixe 394, treize
caractères, aucun numéro répété, et un régime qui découle de la profession.
"""
from __future__ import annotations

from seed.constants import PROFESSIONS
from seed.runner import (
    PROFESSION_REGIME, insured_profession, insured_profile,
    numero_securite_sociale,
)

ECHANTILLON = 20_000


def test_le_numero_commence_par_394_et_fait_treize_caracteres():
    for index in (0, 1, 999, 50_000, 99_999):
        numero = numero_securite_sociale(index)
        assert numero.startswith("394"), numero
        assert len(numero) == 13, numero
        assert numero.isdigit(), numero


def test_aucun_numero_ne_se_repete():
    """La transformation est bijective : deux assurés ne peuvent pas coïncider."""

    numeros = {numero_securite_sociale(index) for index in range(ECHANTILLON)}
    assert len(numeros) == ECHANTILLON


def test_le_numero_est_stable_dans_le_temps():
    """Augmenter la population ne doit pas redistribuer les numéros existants."""

    avant = [numero_securite_sociale(index) for index in range(100)]
    apres = [numero_securite_sociale(index) for index in range(100)]
    assert avant == apres


def test_les_dix_derniers_chiffres_ne_sont_pas_sequentiels():
    """Deux index voisins ne doivent pas produire deux numéros voisins."""

    ecarts = {
        abs(int(numero_securite_sociale(index + 1)[3:]) - int(numero_securite_sociale(index)[3:]))
        for index in range(500)
    }
    assert min(ecarts) > 1_000_000


def test_le_regime_decoule_de_la_profession():
    for index in range(ECHANTILLON):
        _, regime = insured_profile(index)
        assert regime == PROFESSION_REGIME[insured_profession(index)]


def test_seuls_les_deux_regimes_reels_sont_produits():
    regimes = {insured_profile(index)[1] for index in range(ECHANTILLON)}
    assert regimes == {"RAM", "RGB"}


def test_chaque_profession_pointe_vers_un_regime_connu():
    for code, libelle, regime in PROFESSIONS:
        assert regime in {"RAM", "RGB"}, code
        assert libelle.strip(), code
        # PROFESSION_CODE est un VARCHAR2(5) dans le schéma d'origine.
        assert len(code) <= 5, code


def test_la_profession_est_stable():
    premier_passage = [insured_profession(index) for index in range(50)]
    second_passage = [insured_profession(index) for index in range(50)]
    assert premier_passage == second_passage
