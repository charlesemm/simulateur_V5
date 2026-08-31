"""Les quatre paliers de charge du banc d'essai.

Le cahier des charges les nomme et dit ce que chacun sert à vérifier. Le volume
proposé n'est qu'un point de départ : l'écran laisse l'ajuster, parce qu'un
palier est une intention (« un échantillon », « la vraie échelle ») avant
d'être un nombre.
"""

from __future__ import annotations

from dataclasses import dataclass

ECHANTILLON = "ECHANTILLON"
COURANT = "COURANT"
ELEVE = "ELEVE"
AFFLUX = "AFFLUX"

# Bornes du volume acceptées quel que soit le palier. Le plafond protège la
# base de travail : au-delà, la génération se compte en heures.
VOLUME_MINIMUM = 100
VOLUME_MAXIMUM = 5_000_000


@dataclass(frozen=True, slots=True)
class Palier:
    """Un palier de charge, son volume proposé et ce qu'il éprouve."""

    code: str
    libelle: str
    volume_propose: int
    description: str


PALIERS: dict[str, Palier] = {
    ECHANTILLON: Palier(
        ECHANTILLON,
        "Échantillon",
        500,
        "Quelques centaines de lignes, pour vérifier vite après une "
        "modification sans attendre un cycle complet.",
    ),
    COURANT: Palier(
        COURANT,
        "Volume courant",
        100_000,
        "Un volume représentatif de l'activité réelle : la performance dans "
        "les conditions d'usage normales.",
    ),
    ELEVE: Palier(
        ELEVE,
        "Volume élevé",
        500_000,
        "Plusieurs centaines de milliers de lignes : la tenue en charge à "
        "l'échelle de la base CMU complète, pas d'un échantillon.",
    ),
    AFFLUX: Palier(
        AFFLUX,
        "Afflux soudain",
        1_000_000,
        "Un très gros volume transmis d'un seul bloc, comme une campagne "
        "d'enrôlement massive.",
    ),
}


def palier(code: str | None) -> Palier:
    """Retourne le palier demandé, l'échantillon à défaut.

    L'échantillon est le repli volontaire : se tromper de code ne doit jamais
    déclencher une génération d'un million de lignes.
    """

    return PALIERS.get((code or ECHANTILLON).upper(), PALIERS[ECHANTILLON])
