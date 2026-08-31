"""Décrit les types d'anomalies que le simulateur sait injecter.

Le catalogue est la référence : chaque type y porte sa famille, sa cible, sa
sévérité, son interrupteur, son taux et son moment d'entrée en scène. Les
valeurs listées ici servent à peupler TB_REF_ANOMALIES la première fois ;
ensuite, c'est la base qui fait foi.
"""

from __future__ import annotations

from dataclasses import dataclass

# Codes des types injectables. Ils nomment les entrées du catalogue et les
# lignes du journal : ne pas les renommer sans migration.
MONTANT_ABERRANT = "MONTANT_ABERRANT"
MONTANT_HORS_BAREME = "MONTANT_HORS_BAREME"
REPARTITION_FAUSSEE = "REPARTITION_FAUSSEE"
DATE_ANTIDATEE = "DATE_ANTIDATEE"
DATE_SOINS_FUTURE = "DATE_SOINS_FUTURE"
DATE_HORS_DROITS = "DATE_HORS_DROITS"
QUANTITE_EXCESSIVE = "QUANTITE_EXCESSIVE"
QUANTITE_NULLE = "QUANTITE_NULLE"
NUMERO_SECU_INVALIDE = "NUMERO_SECU_INVALIDE"
DATE_NAISSANCE_ABERRANTE = "DATE_NAISSANCE_ABERRANTE"
EMAIL_INVALIDE = "EMAIL_INVALIDE"
TYPE_CENTRE_INCONNU = "TYPE_CENTRE_INCONNU"
PRESTATION_ORPHELINE = "PRESTATION_ORPHELINE"

# Les six familles de la console d'injection, chacune avec sa couleur. Elles
# regroupent les types en boutons ; la famille Référentiel n'a pas encore de
# type, ses codes viendront avec les moteurs.
FAMILLES: dict[str, str] = {
    "MONTANTS": "#b4460c",
    "DATES": "#0369a1",
    "IDENTITE": "#7c3aed",
    "QUANTITES": "#15803d",
    "FORMAT": "#0891b2",
    "REFERENTIEL": "#a16207",
}

# « douce » : la valeur passe les contraintes SQL mais ment sur le métier.
# « dure » : la valeur est manifestement invalide au premier regard.
# ── Les huit dimensions de qualité du cahier des charges ─────────────────
#
# Elles ne remplacent pas les familles : une famille dit *où* l'anomalie est
# posée (montants, dates, identité), une dimension dit *ce qu'elle éprouve*
# chez l'outil testé. C'est la dimension que le cahier des charges emploie, et
# c'est donc elle que la campagne affiche et que le score reprendra.
UNICITE = "UNICITE"
COMPLETUDE = "COMPLETUDE"
VALIDITE = "VALIDITE"
EXACTITUDE = "EXACTITUDE"
TEMPORELLE = "TEMPORELLE"
REFERENTIELLE = "REFERENTIELLE"
CROISEE = "CROISEE"
TECHNIQUE = "TECHNIQUE"

# L'ordre est celui du cahier des charges : il ne se trie pas par nombre de
# types disponibles, sans quoi la liste se réorganiserait à chaque ajout.
DIMENSIONS: dict[str, tuple[str, str]] = {
    UNICITE: (
        "Unicité",
        "Doublons stricts et flous : deux fiches pour la même personne, à une "
        "variation orthographique près.",
    ),
    COMPLETUDE: (
        "Complétude",
        "Champs obligatoires manquants : une immatriculation absente, un nom "
        "de famille vide.",
    ),
    VALIDITE: (
        "Validité (format)",
        "Formats hors normes : une immatriculation qui n'a pas ses treize "
        "chiffres, une adresse électronique mal formée.",
    ),
    EXACTITUDE: (
        "Exactitude (domaine)",
        "Valeurs hors limites : un montant négatif, un taux de prise en "
        "charge étranger au régime de l'assuré.",
    ),
    TEMPORELLE: (
        "Cohérence temporelle",
        "Séquences illogiques : une date de soins antidatée, ou postérieure "
        "au jour de la facture.",
    ),
    REFERENTIELLE: (
        "Intégrité référentielle",
        "Liens rompus entre tables : un code de prestation ou un type "
        "d'établissement qui n'existe dans aucun référentiel.",
    ),
    CROISEE: (
        "Cohérence croisée",
        "Contradictions entre champs : une quantité servie sans prescription, "
        "des soins hors de la période de droits.",
    ),
    TECHNIQUE: (
        "Conformité technique",
        "Caractères cassés à l'import : « N'Guessan » devenu « N?Guessan ».",
    ),
}

SEVERITE_DOUCE = "douce"
SEVERITE_DURE = "dure"

# Moments d'entrée en scène d'un type, réglés par le chantier S3.
#   continu   — pendant toute l'exécution ;
#   demarrage — seulement pendant la fenêtre initiale, puis plus rien ;
#   differe   — rien avant le délai, puis jusqu'à la fin ;
#   manuel    — rien tant que l'opérateur ne l'a pas armé en cours de route.
DECLENCHEMENT_CONTINU = "continu"
DECLENCHEMENT_DEMARRAGE = "demarrage"
DECLENCHEMENT_DIFFERE = "differe"
DECLENCHEMENT_MANUEL = "manuel"

DECLENCHEMENTS = (
    DECLENCHEMENT_CONTINU,
    DECLENCHEMENT_DEMARRAGE,
    DECLENCHEMENT_DIFFERE,
    DECLENCHEMENT_MANUEL,
)

# Fenêtre par défaut, en secondes réelles écoulées depuis le début du run.
DELAI_PAR_DEFAUT = 60


@dataclass(frozen=True, slots=True)
class TypeAnomalie:
    """Un type d'anomalie, sa famille et l'endroit exact qu'il corrompt."""

    code: str
    libelle: str
    famille: str
    table_cible: str
    colonne_cible: str
    severite: str

    @property
    def couleur(self) -> str:
        """Couleur de la famille, celle du bouton dans la console."""

        return FAMILLES[self.famille]

    @property
    def dimension(self) -> str:
        """Dimension de qualité que ce type éprouve chez l'outil testé."""

        return DIMENSION_PAR_CODE[self.code]

    @property
    def dimension_libelle(self) -> str:
        """Nom lisible de la dimension, tel que le cahier des charges l'écrit."""

        return DIMENSIONS[self.dimension][0]


CATALOGUE_INITIAL: tuple[TypeAnomalie, ...] = (
    TypeAnomalie(
        MONTANT_ABERRANT,
        "Montant négatif ou démesuré",
        "MONTANTS",
        "TB_FACTURES_PRESTATIONS",
        "PRESTATION_MONTANT_DEPENSE",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        DATE_ANTIDATEE,
        "Date de soins antidatée jusqu'à un an",
        "DATES",
        "TB_FACTURES",
        "FACTURE_DATE_SOINS",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        QUANTITE_EXCESSIVE,
        "Quantité servie supérieure à la quantité prescrite",
        "QUANTITES",
        "TB_FACTURES_PRESTATIONS",
        "PRESTATION_QUANTITE_SERVIE",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        NUMERO_SECU_INVALIDE,
        "Numéro de sécurité sociale invalide",
        "IDENTITE",
        "TB_REF_ASSURES",
        "NUMERO_SECU",
        SEVERITE_DURE,
    ),
    TypeAnomalie(
        EMAIL_INVALIDE,
        "Adresse électronique invalide",
        "FORMAT",
        "TB_REF_AGENTS",
        "AGENT_EMAIL",
        SEVERITE_DURE,
    ),
    # ── Types ajoutés pour couvrir les six familles ──────────────────────
    TypeAnomalie(
        MONTANT_HORS_BAREME,
        "Taux de remboursement étranger au régime de l'assuré",
        "MONTANTS",
        "TB_FACTURES_PRESTATIONS",
        "PRESTATION_TAUX_REMBOURSEMENT",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        REPARTITION_FAUSSEE,
        "Part CMU et part assuré qui ne recomposent pas la base",
        "MONTANTS",
        "TB_FACTURES_PRESTATIONS",
        "PRESTATION_MONTANT_ASSURE",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        DATE_SOINS_FUTURE,
        "Date de soins postérieure au jour de la facture",
        "DATES",
        "TB_FACTURES",
        "FACTURE_DATE_SOINS",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        DATE_HORS_DROITS,
        "Date de soins tombant hors de la période de droits",
        "DATES",
        "TB_FACTURES",
        "FACTURE_DATE_SOINS",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        QUANTITE_NULLE,
        "Quantité servie nulle alors qu'une quantité est prescrite",
        "QUANTITES",
        "TB_FACTURES_PRESTATIONS",
        "PRESTATION_QUANTITE_SERVIE",
        SEVERITE_DOUCE,
    ),
    TypeAnomalie(
        DATE_NAISSANCE_ABERRANTE,
        "Date de naissance impossible",
        "IDENTITE",
        "TB_REF_ASSURES",
        "ASSURE_DATE_NAISSANCE",
        SEVERITE_DURE,
    ),
    TypeAnomalie(
        TYPE_CENTRE_INCONNU,
        "Type d'établissement absent du référentiel",
        "REFERENTIEL",
        "TB_FACTURES",
        "CENTRE_SANTE_TYPE_CODE",
        SEVERITE_DURE,
    ),
    TypeAnomalie(
        PRESTATION_ORPHELINE,
        "Code de prestation absent du référentiel des actes",
        "REFERENTIEL",
        "TB_FACTURES_PRESTATIONS",
        "PRESTATION_CODE",
        SEVERITE_DURE,
    ),
)

# La dimension éprouvée par chaque type. Elle vit ici et non dans la table :
# c'est une lecture du catalogue, pas un réglage — la changer en base n'aurait
# aucun sens et la ferait diverger du cahier des charges.
#
# Trois dimensions n'ont encore aucun type : l'unicité, la complétude et la
# conformité technique. Leurs injecteurs arrivent au module M5.
DIMENSION_PAR_CODE: dict[str, str] = {
    MONTANT_ABERRANT: EXACTITUDE,
    MONTANT_HORS_BAREME: EXACTITUDE,
    DATE_NAISSANCE_ABERRANTE: EXACTITUDE,
    DATE_ANTIDATEE: TEMPORELLE,
    DATE_SOINS_FUTURE: TEMPORELLE,
    # Des soins hors période de droits, ce n'est pas une date mal formée :
    # c'est la facture qui contredit les droits de l'assuré.
    DATE_HORS_DROITS: CROISEE,
    REPARTITION_FAUSSEE: CROISEE,
    QUANTITE_EXCESSIVE: CROISEE,
    QUANTITE_NULLE: CROISEE,
    NUMERO_SECU_INVALIDE: VALIDITE,
    EMAIL_INVALIDE: VALIDITE,
    TYPE_CENTRE_INCONNU: REFERENTIELLE,
    PRESTATION_ORPHELINE: REFERENTIELLE,
}


CODES = tuple(type_anomalie.code for type_anomalie in CATALOGUE_INITIAL)
