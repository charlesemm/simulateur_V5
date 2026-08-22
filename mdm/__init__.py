"""T2 — Rapprochement d'identités : variantes fabriquées et vérité terrain."""

from mdm.generateur import VARIATIONS, generer_variantes
from mdm.models import MdmPair
from mdm.service import evaluer, lire_paires

__all__ = ["VARIATIONS", "MdmPair", "evaluer", "generer_variantes", "lire_paires"]
