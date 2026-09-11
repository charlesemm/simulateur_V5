"""Données publiques de la CNAM lues par le seed (voir extraire_cnam.py).

Bibliothèque standard seulement : la gouvernance et les tests lisent ces
fichiers sans charger le seed ni ses dépendances.
"""

from __future__ import annotations

import csv
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent

ETABLISSEMENTS = "etablissements_cnam.csv"
PHARMACIES = "pharmacies_cnam.csv"
MEDICAMENTS = "medicaments_cmu.csv"


def lire(nom: str) -> list[dict[str, str]]:
    """Lit un CSV du dossier (UTF-8, séparateur « ; »), dans l'ordre du fichier.

    L'ordre compte : le rang d'une ligne fixe son numéro d'identification.
    """

    with (DOSSIER / nom).open(encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=";"))
