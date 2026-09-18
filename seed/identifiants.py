"""Numéros d'identification : uniques, reproductibles, jamais consécutifs.

Règle fixée par l'utilisateur le 11/09/2026 : aucun numéro d'identification
ne doit se suivre d'une fiche à l'autre, et aucun ne porte de préfixe — que
des chiffres. Deux fiches voisines dans le seed ne doivent donc pas trahir
leur ordre de création, ni même un pas régulier entre leurs numéros.

Le moyen : une permutation à clé (réseau de Feistel en base mixte) du rang
de la fiche dans l'intervalle des nombres à N chiffres sans zéro de tête.
Une permutation est une bijection : deux rangs distincts donnent toujours
deux numéros distincts, sans table ni tirage à vérifier. Et elle est
reproductible : même rang, même nature, même numéro, à chaque seed.

La « nature » (facture, centre, agent…) sert de clé : deux natures ne
produisent pas la même suite, même sur une longueur identique.
"""

from __future__ import annotations

import random
import zlib

# Longueur, en chiffres, de chaque numéro d'identification. C'est la seule
# source de vérité : le seed, le moteur et les tests la lisent ici.
CHIFFRES: dict[str, int] = {
    # Parcours de soins
    "facture": 8,
    # Offre de soins
    "centre": 7,
    "immatriculation_centre": 8,
    "collectivite": 6,
    "pharmacie": 6,
    "medecin_conseil": 4,
    "agent_accueil": 5,
    "agent_gestion": 6,
    "professionnel": 6,
    "numero_ordre": 6,
    # Assurés
    "assure_identifiant": 10,
    "recepisse": 10,
    "droits": 12,
    "piece_identite": 9,
    # Nomenclatures
    "medicament": 6,
    "ean13_article": 9,
    "dci": 5,
    "article_acte": 4,
    "pathologie": 3,
    "sous_chapitre": 2,
    "region": 6,
}

# Rangs réservés au seed. Au-delà, les numéros tirés à l'exécution (inscription,
# MDM, entrepôt) ne peuvent pas retomber sur un numéro déjà semé : la
# permutation étant une bijection, des rangs disjoints donnent des numéros
# disjoints. Le plus gros volume semé, les droits (100 000 assurés x 12 mois),
# tient largement dessous.
RANGS_SEED = 2_000_000

TOURS = 4


def taille(chiffres: int) -> int:
    """Nombre de numéros à N chiffres sans zéro de tête (de 10^(N-1) à 10^N - 1)."""

    return 9 * 10 ** (chiffres - 1)


def _tour(nature: str, numero_tour: int, valeur: int) -> int:
    """Fonction de tour : un condensé stable (crc32), jamais hash() qui varie
    d'un processus à l'autre."""

    return zlib.crc32(f"{nature}:{numero_tour}:{valeur}".encode())


def brouiller(rang: int, chiffres: int, nature: str) -> str:
    """Rang (0, 1, 2…) -> numéro de `chiffres` chiffres, propre à `nature`.

    Le rang est découpé en deux moitiés (base mixte 9·10^k × 10^m, dont le
    produit est exactement la taille de l'intervalle) ; chaque tour ajoute à
    une moitié un condensé de l'autre, modulo sa propre base. Chaque tour est
    inversible, le tout est donc une permutation de l'intervalle.
    """

    etendue = taille(chiffres)
    if not 0 <= rang < etendue:
        raise ValueError(f"Rang {rang} hors de l'intervalle à {chiffres} chiffres.")

    k = (chiffres - 1) // 2
    base_gauche, base_droite = 9 * 10 ** k, 10 ** (chiffres - 1 - k)
    gauche, droite = divmod(rang, base_droite)
    for numero_tour in range(TOURS):
        if numero_tour % 2 == 0:
            gauche = (gauche + _tour(nature, numero_tour, droite)) % base_gauche
        else:
            droite = (droite + _tour(nature, numero_tour, gauche)) % base_droite
    return str(10 ** (chiffres - 1) + gauche * base_droite + droite)


def numero(nature: str, rang: int) -> str:
    """Numéro d'identification d'une nature déclarée dans CHIFFRES."""

    return brouiller(rang, CHIFFRES[nature], nature)


def numero_libre(nature: str, tirage: random.Random) -> str:
    """Numéro tiré à l'exécution, garanti distinct de tout numéro semé."""

    rang = RANGS_SEED + tirage.randrange(taille(CHIFFRES[nature]) - RANGS_SEED)
    return numero(nature, rang)


# ── Numéro de sécurité sociale ───────────────────────────────────────────
#
# Format fixé à part (10/09/2026) : « 394 » suivi de dix chiffres, soit
# treize caractères. Le préfixe est une donnée, pas un compteur : il reste.
# Les dix chiffres viennent d'une bijection affine sur 10^10 — le
# multiplicateur est impair et non divisible par cinq, il n'a donc aucun
# diviseur commun avec le modulo.
SECU_MULTIPLICATEUR = 3_141_592_653
SECU_DECALAGE = 2_718_281_829
SECU_MODULO = 10 ** 10


def numero_securite_sociale(index: int) -> str:
    """Produit un numéro de treize caractères commençant par 394.

    Les dix chiffres suivants paraissent tirés au hasard mais restent uniques
    et stables : un même index redonne toujours le même numéro, et augmenter
    le nombre d'assurés ne redistribue pas ceux qui existent déjà.
    """

    suffixe = (SECU_MULTIPLICATEUR * index + SECU_DECALAGE) % SECU_MODULO
    return f"394{suffixe:010d}"


def numero_securite_sociale_libre(tirage: random.Random) -> str:
    """Numéro de sécurité sociale tiré à l'exécution, hors des rangs semés."""

    return numero_securite_sociale(RANGS_SEED + tirage.randrange(SECU_MODULO - RANGS_SEED))
