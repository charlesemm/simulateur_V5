"""Vérifie les identifiants et le régime produits par le seed, sans base.

Règles fixées par l'utilisateur : le numéro de sécurité sociale commence par
394 et fait treize caractères ; tous les autres numéros d'identification
n'ont pas de préfixe, ne contiennent que des chiffres et ne se suivent
jamais d'une fiche à l'autre (11/09/2026). Aucun numéro n'est répété, et le
régime découle de la profession.
"""
from __future__ import annotations

import random

from seed.constants import PROFESSIONS
from seed.identifiants import (
    CHIFFRES, brouiller, numero, numero_libre, numero_securite_sociale_libre,
    taille,
)
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


# ── Numéros sans préfixe, jamais consécutifs ─────────────────────────────

# Volumes réellement semés (ou produits sur une longue exécution) : c'est sur
# eux que la règle « jamais deux numéros voisins » doit tenir.
VOLUMES = {
    "facture": 20_000, "centre": 1_510, "agent_accueil": 1_510,
    "medecin_conseil": 20, "professionnel": 3_020, "assure_identifiant": 20_000,
    "recepisse": 20_000, "medicament": 918,
}


def test_la_permutation_couvre_tout_l_intervalle_sans_doublon():
    for chiffres in (1, 2, 3, 4):
        numeros = [brouiller(rang, chiffres, "test") for rang in range(taille(chiffres))]
        assert len(set(numeros)) == taille(chiffres)
        assert all(len(valeur) == chiffres and valeur[0] != "0" for valeur in numeros)


def test_chaque_nature_a_la_longueur_declaree_et_que_des_chiffres():
    for nature, chiffres in CHIFFRES.items():
        for rang in (0, 1, 2, taille(chiffres) - 1):
            valeur = numero(nature, rang)
            assert valeur.isdigit(), nature
            assert len(valeur) == chiffres and valeur[0] != "0", nature


def test_deux_fiches_voisines_n_ont_jamais_deux_numeros_voisins():
    for nature, volume in VOLUMES.items():
        voisins = [
            rang for rang in range(volume - 1)
            if abs(int(numero(nature, rang + 1)) - int(numero(nature, rang))) == 1
        ]
        assert not voisins, (nature, voisins[:5])


def test_l_ecart_entre_deux_numeros_n_est_pas_constant():
    """Un pas fixe trahirait l'ordre de création aussi sûrement qu'un compteur."""

    ecarts = {int(numero("facture", rang + 1)) - int(numero("facture", rang))
              for rang in range(500)}
    assert len(ecarts) > 450


def test_deux_natures_de_meme_longueur_ne_suivent_pas_la_meme_suite():
    assert ([numero("pharmacie", rang) for rang in range(20)]
            != [numero("collectivite", rang) for rang in range(20)])


def test_un_numero_tire_a_l_execution_ne_retombe_jamais_sur_un_numero_seme():
    tirage = random.Random(7)
    semes = {numero("recepisse", rang) for rang in range(50_000)}
    libres = {numero_libre("recepisse", tirage) for _ in range(2_000)}
    assert not semes & libres
    assert numero_securite_sociale_libre(tirage).startswith("394")
