"""T2 — Rapprochement d'identités : variantes fabriquées et vérité terrain."""

from echo.metier.mdm.generateur import VARIATIONS, generer_variantes
from echo.metier.mdm.models import MdmPair
from echo.metier.mdm.service import evaluer, lire_paires

__all__ = ["VARIATIONS", "MdmPair", "evaluer", "generer_variantes", "lire_paires"]
