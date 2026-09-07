"""Module « Qualité des données » : les campagnes de test.

Une campagne est l'unité indivisible du cahier des charges : un jeu de données
piégé, son corrigé, les paramètres qui l'ont produit, le rapport de l'outil
testé et le résultat du rapprochement. Elle ne se confond pas avec une
exécution du moteur (`TB_SIMULATIONS`) : une campagne n'a ni vitesse ni
passages simultanés, elle a un volume, une graine et un score.
"""

from campagnes.echange import historique, transmettre
from campagnes.generation import (
    Progression, compter_corrige, lancer, lire_corrige, progression,
)
from campagnes.models import (
    Campagne, CorrigeCampagne, EchangeCampagne, STATUT_CREEE, STATUT_GENEREE,
    STATUT_GENERATION, STATUTS,
)
from campagnes.paliers import PALIERS, Palier, palier
from campagnes.service import (
    creer, dimensions_couvertes, lire, lister, normaliser_anomalies,
    previsualiser_reference,
)

__all__ = [
    "Campagne",
    "CorrigeCampagne",
    "EchangeCampagne",
    "Progression",
    "PALIERS",
    "Palier",
    "STATUTS",
    "STATUT_CREEE",
    "STATUT_GENERATION",
    "STATUT_GENEREE",
    "compter_corrige",
    "creer",
    "dimensions_couvertes",
    "historique",
    "lancer",
    "lire",
    "lire_corrige",
    "lister",
    "progression",
    "normaliser_anomalies",
    "palier",
    "previsualiser_reference",
    "transmettre",
]
