"""Vérifie ce que le contexte de construction de l'image laisse dehors.

« COPY . . » recopie tout ce que .containerignore n'exclut pas. Les données
exclues de Git par .gitignore n'étaient pas exclues de l'image : une
construction faite depuis un poste les embarquait (AUDIT A08). La CI, partie
d'un checkout qui ne les contient pas, ne pouvait pas le voir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _exclusions() -> set[str]:
    lignes = (RACINE / ".containerignore").read_text(encoding="utf-8").splitlines()
    return {ligne.strip() for ligne in lignes if ligne.strip() and not ligne.startswith("#")}


@pytest.mark.parametrize("chemin", [
    ".env",
    # Extraits CSV de tables de production et captures d'écran.
    "assuré",
    "FSE.pptx",
    # Environnement Python et caches du poste.
    ".local/",
    ".cache/",
    ".venv/",
])
def test_le_contexte_de_construction_exclut(chemin):
    assert chemin in _exclusions(), f"« {chemin} » entrerait dans l'image."
