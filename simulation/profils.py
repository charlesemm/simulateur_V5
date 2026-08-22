"""Les quatre types de simulation d'ÉCHO, et ce que chacun règle.

Les quatre boutons ne sont pas quatre habillages du même moteur : chacun change
ce qui est produit. Ce module ne contient que les profils de paramètres — les
moteurs eux-mêmes viennent avec T1 à T4. Un profil dit, pour son type :
combien de passages à la fois, à quelle vitesse, quelles anomalies à quel taux
et à quel moment, et quels aléas.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from anomalies.catalogue import (
    DATE_ANTIDATEE, DECLENCHEMENT_CONTINU, DECLENCHEMENT_DIFFERE,
    EMAIL_INVALIDE, MONTANT_ABERRANT, NUMERO_SECU_INVALIDE, QUANTITE_EXCESSIVE,
)
from simulation.aleas import BASE_RALENTIE, COUPURE_BRUTALE, RAFALE
from simulation_config import DEFAULT_CONFIG, SimulationConfig

QUALITE = "QUALITE"
MDM = "MDM"
ENTREPOT = "ENTREPOT"
GOUVERNANCE = "GOUVERNANCE"

TYPES = (QUALITE, MDM, ENTREPOT, GOUVERNANCE)


@dataclass(frozen=True, slots=True)
class ProfilSimulation:
    """Le réglage complet d'un type de simulation."""

    code: str
    libelle: str
    description: str
    vitesse: float
    passages_simultanes_max: int
    # Réglage par type d'anomalie : taux, déclenchement, délai.
    anomalies: dict[str, dict] = field(default_factory=dict)
    # Réglage par aléa : probabilité et paramètres propres.
    aleas: dict[str, dict] = field(default_factory=dict)
    # Ce que le type produit en plus des passages, avant que le moteur ne
    # démarre. C'est ce qui fait que quatre boutons ne sont pas quatre
    # habillages du même moteur.
    preparation: dict[str, int] = field(default_factory=dict)

    def config_moteur(self, base: SimulationConfig = DEFAULT_CONFIG) -> SimulationConfig:
        """Applique le profil à la configuration du moteur."""

        return replace(
            base,
            default_speed=self.vitesse,
            max_concurrent_passages=self.passages_simultanes_max,
        )


PROFILS: dict[str, ProfilSimulation] = {
    QUALITE: ProfilSimulation(
        code=QUALITE,
        libelle="Qualité des données",
        description=(
            "Produit un flux courant, largement corrompu, pour éprouver la "
            "détection : complétude, validité, unicité, cohérence."
        ),
        vitesse=60,
        passages_simultanes_max=20,
        # Le type le plus généreux en anomalies : c'est ce qu'il vient tester.
        anomalies={
            MONTANT_ABERRANT: {"taux": 0.15, "declenchement": DECLENCHEMENT_CONTINU},
            DATE_ANTIDATEE: {"taux": 0.15, "declenchement": DECLENCHEMENT_CONTINU},
            QUANTITE_EXCESSIVE: {"taux": 0.10, "declenchement": DECLENCHEMENT_CONTINU},
            EMAIL_INVALIDE: {"taux": 0.05, "declenchement": DECLENCHEMENT_CONTINU},
        },
        aleas={},
    ),
    MDM: ProfilSimulation(
        code=MDM,
        libelle="Rapprochement d'identités",
        description=(
            "Vise l'identité : numéros invalides et variantes, pour éprouver "
            "le rapprochement. Les identités volontairement jumelles et leur "
            "vérité terrain viennent avec le moteur T2."
        ),
        vitesse=60,
        passages_simultanes_max=20,
        anomalies={
            NUMERO_SECU_INVALIDE: {"taux": 0.20, "declenchement": DECLENCHEMENT_CONTINU},
            EMAIL_INVALIDE: {"taux": 0.10, "declenchement": DECLENCHEMENT_CONTINU},
        },
        aleas={},
        # Les identités jumelles et leur vérité terrain sont fabriquées au
        # lancement : sans elles, ce type ne se distinguerait pas des autres.
        preparation={"mdm_variantes": 50},
    ),
    ENTREPOT: ProfilSimulation(
        code=ENTREPOT,
        libelle="Entrepôt de données",
        description=(
            "Cherche le volume et la profondeur d'historique plutôt que le "
            "défaut : beaucoup de passages, très accélérés, peu d'anomalies."
        ),
        vitesse=600,
        passages_simultanes_max=100,
        anomalies={
            MONTANT_ABERRANT: {"taux": 0.01, "declenchement": DECLENCHEMENT_CONTINU},
        },
        # Le volume est justement l'occasion d'éprouver une base qui ralentit.
        aleas={
            RAFALE: {"probabilite": 0.05, "taille": 50},
            BASE_RALENTIE: {"probabilite": 0.02, "latence_secondes": 0.3},
        },
        # La profondeur d'historique est produite d'emblée : c'est elle qu'un
        # chargement d'entrepôt vient éprouver, pas le flux du jour.
        preparation={"historique_mois": 12, "historique_assures": 100},
    ),
    GOUVERNANCE: ProfilSimulation(
        code=GOUVERNANCE,
        libelle="Gouvernance",
        description=(
            "Produit des violations de règles et des cas de conformité. Les "
            "anomalies entrent en cours de route, pour que l'avant et l'après "
            "soient comparables dans la même exécution."
        ),
        vitesse=60,
        passages_simultanes_max=20,
        anomalies={
            MONTANT_ABERRANT: {
                "taux": 0.25,
                "declenchement": DECLENCHEMENT_DIFFERE,
                "delai_secondes": 120,
            },
            DATE_ANTIDATEE: {
                "taux": 0.25,
                "declenchement": DECLENCHEMENT_DIFFERE,
                "delai_secondes": 120,
            },
        },
        # La coupure éprouve ce que devient la piste d'audit quand tout casse.
        aleas={COUPURE_BRUTALE: {"probabilite": 0.02}},
    ),
}


def profil(code: str | None) -> ProfilSimulation:
    """Retourne le profil demandé, celui de la qualité des données à défaut."""

    return PROFILS.get((code or QUALITE).upper(), PROFILS[QUALITE])
