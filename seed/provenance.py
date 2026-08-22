"""D'où vient chaque référentiel, et ce qui reste à confirmer avec la CNAM.

Une bonne partie des listes du seed a été reconstituée faute d'avoir les
nomenclatures officielles. Le problème n'est pas qu'elles soient inventées —
il faut bien peupler la base — mais qu'une fois en base, rien ne les distingue
des vraies. Un jeu de données livré au MDM ou à l'entrepôt porte alors des
codes qui n'existent nulle part ailleurs, sans que personne ne le sache.

Ce registre rend la distinction explicite et interrogeable. Il ne corrige
rien : il dit ce qui est à confronter, et pourquoi.
"""

from __future__ import annotations

from dataclasses import dataclass

from seed.constants import (
    COUNTRIES, HEALTH_CENTER_TYPES, INVOICE_TYPES, IVORIAN_CITIES,
    IVORIAN_DISTRICTS, MEDICAL_ACTS, MEDICAL_SPECIALTIES, MEDICATION_SEEDS,
    PATHOLOGY_LABELS, PROFESSIONS, TYPES_IDENTIFIANTS,
)

# Nature d'un référentiel, du plus sûr au plus fragile.
OFFICIEL = "officiel"
VRAISEMBLABLE = "vraisemblable"
INVENTE = "invente"

LIBELLES_NATURE = {
    OFFICIEL: "Repris d'une source officielle",
    VRAISEMBLABLE: "Reconstitué, plausible mais non vérifié",
    INVENTE: "Inventé pour les besoins du simulateur",
}


@dataclass(frozen=True, slots=True)
class Referentiel:
    """Un référentiel du seed, sa provenance et ce qu'il faut en faire."""

    cle: str
    libelle: str
    nature: str
    entrees: int
    table_cible: str
    note: str


@dataclass(frozen=True, slots=True)
class Hypothese:
    """Un chiffre choisi faute de mieux, avec ce qui l'a dicté."""

    cle: str
    libelle: str
    valeur: str
    fondement: str
    consequence: str


REFERENTIELS: tuple[Referentiel, ...] = (
    Referentiel(
        "TYPES_IDENTIFIANTS", "Types de pièces d'identité", INVENTE,
        len(TYPES_IDENTIFIANTS), "TB_ASSURES_IDENTIFIANTS",
        "Les six codes tiennent dans le VARCHAR(6) de la colonne, mais aucun "
        "ne vient d'une nomenclature CNAM.",
    ),
    Referentiel(
        "PROFESSIONS", "Professions et régime associé", INVENTE,
        len(PROFESSIONS), "TB_ASSURES_PROFESSIONS",
        "C'est le référentiel le plus lourd de conséquences : le troisième "
        "champ décide du régime, donc du taux de remboursement.",
    ),
    Referentiel(
        "IVORIAN_DISTRICTS", "Districts de Côte d'Ivoire", VRAISEMBLABLE,
        len(IVORIAN_DISTRICTS), "TB_TV_LOCALISATION_REGIONS",
        "Les quatorze districts existent bien ; leur usage comme niveau "
        "« région » du découpage CNAM reste à valider.",
    ),
    Referentiel(
        "IVORIAN_CITIES", "Localités", VRAISEMBLABLE,
        len(IVORIAN_CITIES), "TB_TV_LOCALISATION_LOCALITES",
        "Villes réelles, mais leur rattachement aux départements est arbitraire.",
    ),
    Referentiel(
        "COUNTRIES", "Pays de naissance", OFFICIEL,
        len(COUNTRIES), "TB_TV_LOCALISATION_PAYS",
        "Codes ISO 3166 et codes numériques officiels. Seule la liste des huit "
        "pays retenus est un choix du simulateur.",
    ),
    Referentiel(
        "HEALTH_CENTER_TYPES", "Types d'établissement sanitaire", VRAISEMBLABLE,
        len(HEALTH_CENTER_TYPES), "TB_REF_CENTRES_SANTE",
        "Reprend la terminologie sanitaire ivoirienne courante.",
    ),
    Referentiel(
        "MEDICAL_SPECIALTIES", "Spécialités médicales", VRAISEMBLABLE,
        len(MEDICAL_SPECIALTIES), "TB_REF_SPECIALITES_MEDICALES",
        "Spécialités universelles ; les codes sont propres au simulateur.",
    ),
    Referentiel(
        "PATHOLOGY_LABELS", "Pathologies", VRAISEMBLABLE,
        len(PATHOLOGY_LABELS), "TB_REF_PATHOLOGIES",
        "Pathologies réelles, mais sans codage CIM-10 : un outil qui attend la "
        "CIM ne retrouvera pas ses petits.",
    ),
    Referentiel(
        "MEDICATION_SEEDS", "Médicaments", VRAISEMBLABLE,
        len(MEDICATION_SEEDS), "TB_REF_MEDICAMENTS",
        "Dénominations communes réelles ; les tarifs sont indicatifs.",
    ),
    Referentiel(
        "MEDICAL_ACTS", "Actes médicaux", INVENTE,
        len(MEDICAL_ACTS), "TB_REF_ACTES_MEDICAUX",
        "Les préfixes BIO-, IMG- et HOS- pilotent le moteur d'entente "
        "préalable : les changer change le comportement du simulateur.",
    ),
    Referentiel(
        "INVOICE_TYPES", "Types de facture", INVENTE,
        len(INVOICE_TYPES), "TB_TV_TYPES_FACTURES",
        "AMB et DEN suffisent au parcours simulé ; la nomenclature réelle est "
        "certainement plus riche.",
    ),
)


# Part des professions qui ouvrent droit à chaque régime : ce n'est pas un
# choix, c'est la conséquence arithmétique de la liste ci-dessus.
_RAM = sum(1 for entree in PROFESSIONS if entree[2] == "RAM")
_PART_RAM = round(100 * _RAM / len(PROFESSIONS), 1)

HYPOTHESES: tuple[Hypothese, ...] = (
    Hypothese(
        "TAUX_COUVERTURE", "Part des assurés aux droits ouverts", "60 %",
        "Choisi pour que le simulateur produise des passages ; les volumes "
        "réels suggèrent une proportion bien plus faible.",
        "Un taux réaliste ferait refuser presque tous les passages à "
        "l'accueil — d'où le registre des refus, qui rend enfin ce cas "
        "mesurable. Réglable par la variable d'environnement TAUX_COUVERTURE.",
    ),
    Hypothese(
        "REPARTITION_REGIMES", "Répartition RAM / RGB",
        f"{_PART_RAM} % RAM, {round(100 - _PART_RAM, 1)} % RGB",
        "Découle du nombre de codes de professions rattachés à chaque régime, "
        "pas d'une réalité démographique.",
        "Le taux de remboursement moyen des jeux de données en dépend "
        "directement : 100 % pour le RAM contre 70 % pour le RGB.",
    ),
    Hypothese(
        "ANNEE_DROITS", "Année des droits peuplés par le seed", "2026",
        "Année en cours au moment de l'écriture du seed.",
        "Les droits d'autres années viennent du moteur d'entrepôt (T3), pas "
        "du seed.",
    ),
)


def resume() -> dict[str, int]:
    """Compte les référentiels par nature, pour l'écran de gouvernance."""

    comptes = {nature: 0 for nature in LIBELLES_NATURE}
    for referentiel in REFERENTIELS:
        comptes[referentiel.nature] += 1
    return comptes
