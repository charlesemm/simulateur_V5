"""Scénarios d'aléa : les pannes que le simulateur sait jouer.

Un aléa n'est pas une anomalie. L'anomalie fausse une valeur, l'aléa maltraite
le déroulement : le moteur s'arrête au milieu d'une facture, la base répond
lentement, la connexion tombe, l'horloge dérape. Ce sont les crash tests — ce
qui révèle si les données restent cohérentes quand tout ne se passe pas bien.

Chacun est réglable par probabilité, déclenchable à la main pendant une
exécution, journalisé comme événement, et rejouable à l'identique : les tirages
passent par le générateur ensemencé du passage.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# Le moteur s'arrête net au milieu d'un passage : la facture reste ouverte,
# sans prestation ni clôture. C'est l'aléa qui éprouve la cohérence.
COUPURE_BRUTALE = "COUPURE_BRUTALE"
# Une salve de passages part d'un coup, au lieu du flux régulier.
RAFALE = "RAFALE"
# Chaque écriture attend, comme une base saturée.
BASE_RALENTIE = "BASE_RALENTIE"
# Une écriture échoue franchement : le passage est perdu.
PERTE_CONNEXION = "PERTE_CONNEXION"
# L'horloge simulée du passage part en avant ou en arrière.
HORLOGE_DECALEE = "HORLOGE_DECALEE"
# Le processus retient de la mémoire le temps du passage.
SATURATION_MEMOIRE = "SATURATION_MEMOIRE"

ALEAS = (
    COUPURE_BRUTALE, RAFALE, BASE_RALENTIE,
    PERTE_CONNEXION, HORLOGE_DECALEE, SATURATION_MEMOIRE,
)

LIBELLES: dict[str, str] = {
    COUPURE_BRUTALE: "Coupure brutale en pleine transaction",
    RAFALE: "Génération massive en rafale",
    BASE_RALENTIE: "Base de données ralentie",
    PERTE_CONNEXION: "Perte de connexion à la base",
    HORLOGE_DECALEE: "Horloge décalée",
    SATURATION_MEMOIRE: "Saturation mémoire",
}

# Réglages par défaut de chaque aléa, tous à l'arrêt.
DEFAUTS: dict[str, dict[str, float]] = {
    COUPURE_BRUTALE: {"probabilite": 0.0},
    RAFALE: {"probabilite": 0.0, "taille": 25},
    BASE_RALENTIE: {"probabilite": 0.0, "latence_secondes": 0.5},
    PERTE_CONNEXION: {"probabilite": 0.0},
    HORLOGE_DECALEE: {"probabilite": 0.0, "amplitude_heures": 72},
    SATURATION_MEMOIRE: {"probabilite": 0.0, "megaoctets": 50},
}


class PassageInterrompu(RuntimeError):
    """Lève l'arrêt volontaire d'un passage, au titre d'un aléa."""

    def __init__(self, alea: str) -> None:
        super().__init__(f"Passage interrompu par l'aléa {alea}.")
        self.alea = alea


@dataclass
class ScenarioAleas:
    """Les aléas retenus pour une exécution, avec leurs réglages."""

    reglages: dict[str, dict[str, float]] = field(
        default_factory=lambda: {code: dict(valeurs) for code, valeurs in DEFAUTS.items()}
    )
    # Aléas armés à la main par l'opérateur : ils frappent au prochain passage,
    # une seule fois, puis se désarment.
    armes: set[str] = field(default_factory=set)

    @classmethod
    def depuis_parametres(cls, parametres: dict | None) -> ScenarioAleas:
        """Reconstruit un scénario depuis ce qui est stocké sur l'exécution."""

        scenario = cls()
        for code, valeurs in (parametres or {}).items():
            if code in scenario.reglages and isinstance(valeurs, dict):
                scenario.reglages[code].update(valeurs)
        return scenario

    def en_parametres(self) -> dict[str, dict[str, float]]:
        """Retourne les seuls aléas réellement activés, pour l'exécution."""

        return {
            code: dict(valeurs)
            for code, valeurs in self.reglages.items()
            if valeurs.get("probabilite", 0)
        }

    def reglage(self, code: str, nom: str, defaut: float) -> float:
        """Lit un paramètre d'aléa, avec son défaut si personne ne l'a réglé."""

        return self.reglages.get(code, {}).get(nom, defaut)

    def armer(self, code: str) -> None:
        """Arme un aléa : il frappera au prochain passage, puis se désarmera."""

        if code in self.reglages:
            self.armes.add(code)

    def frappe(self, code: str, tirage: random.Random) -> bool:
        """Dit si l'aléa frappe ce passage-ci, par tirage ou parce qu'il est armé.

        Un aléa armé à la main l'emporte sur la probabilité : c'est un ordre,
        pas une chance. Il ne vaut que pour un passage.
        """

        if code in self.armes:
            self.armes.discard(code)
            return True
        probabilite = self.reglage(code, "probabilite", 0.0)
        # Aucun tirage quand l'aléa est à l'arrêt : sans cette garde, activer
        # les aléas déplacerait la suite aléatoire et un passage de même graine
        # ne se rejouerait plus à l'identique.
        if probabilite <= 0:
            return False
        return tirage.random() < probabilite
