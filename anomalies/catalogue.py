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

CODES = tuple(type_anomalie.code for type_anomalie in CATALOGUE_INITIAL)
