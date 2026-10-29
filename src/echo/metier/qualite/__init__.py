"""T1 — Moteur de qualité des données, confronté à la vérité terrain."""

from echo.metier.qualite.regles import COHERENCE, COMPLETUDE, DIMENSIONS, REGLES, UNICITE, VALIDITE
from echo.metier.qualite.service import analyser

__all__ = [
    "COHERENCE", "COMPLETUDE", "DIMENSIONS", "REGLES", "UNICITE", "VALIDITE",
    "analyser",
]
