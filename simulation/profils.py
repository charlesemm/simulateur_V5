"""Les cinq types de simulation d'ÉCHO, et ce que chacun règle.

Le mode LIBRE est le bac à sable : aucune anomalie pré-configurée, aucune
préparation préalable — l'opérateur compose sa recette à la main dans l'écran
de lancement, puis déclenche les aléas depuis le cockpit. Les quatre autres
types (QUALITE, MDM, ENTREPOT, GOUVERNANCE) proposent un réglage de départ
adapté à chaque objectif, modifiable avant lancement.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from anomalies.catalogue import (
    DATE_ANTIDATEE, DECLENCHEMENT_CONTINU, DECLENCHEMENT_DIFFERE,
    EMAIL_INVALIDE, MONTANT_ABERRANT, NUMERO_SECU_INVALIDE, QUANTITE_EXCESSIVE,
)
from simulation_config import DEFAULT_CONFIG, SimulationConfig

LIBRE = "LIBRE"
QUALITE = "QUALITE"
MDM = "MDM"
ENTREPOT = "ENTREPOT"
GOUVERNANCE = "GOUVERNANCE"

TYPES = (LIBRE, QUALITE, MDM, ENTREPOT, GOUVERNANCE)

# Les deux parcours qu'une carte de l'accueil peut ouvrir.
PARCOURS_MOTEUR = "moteur"
PARCOURS_CAMPAGNE = "campagne"


@dataclass(frozen=True, slots=True)
class ProfilSimulation:
    """Le réglage complet d'un type de simulation."""

    code: str
    libelle: str
    description: str
    # Couleur du type, pour que l'accueil distingue les quatre d'un coup d'œil
    # sans que l'interface ait à les connaître par leur nom.
    couleur: str
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
    # Ouvert ou en attente de son cahier des charges. C'est le serveur qui le
    # dit : l'accueil grisait les types dans son propre code, si bien qu'en
    # ouvrir un demandait de retoucher le navigateur.
    disponible: bool = False
    # Où mène la carte quand on la clique. MOTEUR ouvre le paramétrage d'une
    # exécution du moteur temps réel ; CAMPAGNE ouvre une campagne de test du
    # module Qualité des données, qui ne passe pas par le moteur.
    parcours: str | None = None

    def config_moteur(self, base: SimulationConfig = DEFAULT_CONFIG) -> SimulationConfig:
        """Applique le profil à la configuration du moteur."""

        return replace(
            base,
            default_speed=self.vitesse,
            max_concurrent_passages=self.passages_simultanes_max,
        )


PROFILS: dict[str, ProfilSimulation] = {
    LIBRE: ProfilSimulation(
        code=LIBRE,
        libelle="Simulation libre",
        description=(
            "Le bac à sable : aucune anomalie pré-configurée, tout se compose "
            "à la main. Choisissez vos anomalies, réglez vos taux, et déclenchez "
            "les aléas en direct depuis le cockpit."
        ),
        couleur="#e5484d",
        vitesse=60,
        passages_simultanes_max=20,
        # Rien de pré-coché : c'est le principe du mode libre.
        anomalies={},
        aleas={},
        disponible=True,
        parcours=PARCOURS_MOTEUR,
    ),
    QUALITE: ProfilSimulation(
        code=QUALITE,
        libelle="Qualité des données",
        description=(
            "Fabrique un jeu de données piégé et son corrigé, le transmet à "
            "l'outil de qualité à tester, puis note ce qu'il a su détecter."
        ),
        couleur="#16a34a",
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
        # Ouvert depuis le cahier des charges du 2026-08-28. Ce type ne lance
        # pas le moteur : il ouvre une campagne de test, où ÉCHO fabrique un
        # jeu piégé pour noter un outil de qualité extérieur.
        disponible=True,
        parcours=PARCOURS_CAMPAGNE,
    ),
    MDM: ProfilSimulation(
        code=MDM,
        libelle="Rapprochement d'identités",
        description=(
            "Vise l'identité : numéros invalides et variantes, pour éprouver "
            "le rapprochement. Les identités volontairement jumelles et leur "
            "vérité terrain viennent avec le moteur T2."
        ),
        couleur="#7c3aed",
        vitesse=60,
        passages_simultanes_max=20,
        anomalies={
            NUMERO_SECU_INVALIDE: {"taux": 0.20, "declenchement": DECLENCHEMENT_CONTINU},
            EMAIL_INVALIDE: {"taux": 0.10, "declenchement": DECLENCHEMENT_CONTINU},
        },
        aleas={},
        # Les identités jumelles viendront avec le moteur T2 (cahier des
        # charges en attente). En attendant, le profil sert d'amorce
        # d'anomalies centrées sur l'identité.
    ),
    ENTREPOT: ProfilSimulation(
        code=ENTREPOT,
        libelle="Entrepôt de données",
        description=(
            "Cherche le volume et la profondeur d'historique plutôt que le "
            "défaut : beaucoup de passages, très accélérés, peu d'anomalies."
        ),
        couleur="#0284c7",
        vitesse=600,
        passages_simultanes_max=100,
        anomalies={
            MONTANT_ABERRANT: {"taux": 0.01, "declenchement": DECLENCHEMENT_CONTINU},
        },
        # Aucun aléa d'office : ils se déclenchent à la main.
        aleas={},
        # L'historique SCD2 viendra avec le moteur T3 (cahier des charges en
        # attente). En attendant, le profil configure beaucoup de volume.
    ),
    GOUVERNANCE: ProfilSimulation(
        code=GOUVERNANCE,
        libelle="Gouvernance",
        description=(
            "Produit des violations de règles et des cas de conformité. Les "
            "anomalies entrent en cours de route, pour que l'avant et l'après "
            "soient comparables dans la même exécution."
        ),
        couleur="#a16207",
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
        # Comme les autres types : les aléas se déclenchent à la main.
        aleas={},
    ),
}


def profil(code: str | None) -> ProfilSimulation:
    """Retourne le profil demandé, celui de la qualité des données à défaut."""

    return PROFILS.get((code or QUALITE).upper(), PROFILS[QUALITE])
