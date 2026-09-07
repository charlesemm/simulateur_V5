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

# ── Les six types du chapitre 5 ─────────────────────────────────────────
#
# Ils comblent les trois dimensions que rien ne savait encore éprouver :
# Unicité, Complétude et Conformité technique.
#
# **Ils s'ajoutent en fin de liste, jamais au milieu.** L'ordre du catalogue
# fixe l'ordre des tirages du générateur : insérer un code avant les autres
# décalerait tous les tirages suivants et changerait l'intégralité des
# fichiers déjà produits, à graine pourtant constante.
DOUBLON_EXACT = "DOUBLON_EXACT"
DOUBLON_APPROCHANT = "DOUBLON_APPROCHANT"
CHAMP_OBLIGATOIRE_VIDE = "CHAMP_OBLIGATOIRE_VIDE"
ENCODAGE_CASSE = "ENCODAGE_CASSE"
FORMAT_DATE_INCOHERENT = "FORMAT_DATE_INCOHERENT"
TENTATIVE_INJECTION = "TENTATIVE_INJECTION"

# ── Portée d'un type ────────────────────────────────────────────────────
#
# Tous les types ne peuvent pas être posés partout. Un doublon suppose de
# connaître une ligne déjà écrite ; le moteur temps réel, lui, traite un
# passage à la fois, en concurrence, sans mémoire de ce qui précède. Lui
# proposer ces types afficherait des boutons sans effet — ce que le projet
# s'interdit : ce qu'on montre doit marcher.
PORTEE_TOUTES = "toutes"
PORTEE_CAMPAGNE = "campagne"

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
    # Par défaut un type vaut partout ; seuls ceux qui exigent une mémoire des
    # lignes déjà écrites sont réservés à la campagne.
    portee: str = PORTEE_TOUTES

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
    # ── Chapitre 5 : les familles qui manquaient ────────────────────────
    TypeAnomalie(
        DOUBLON_EXACT,
        "Deux fiches strictement identiques pour la même personne",
        "IDENTITE",
        "TB_REF_ASSURES",
        "ASSURE_NUMERO_IDENTIFIANT",
        SEVERITE_DURE,
        PORTEE_CAMPAGNE,
    ),
    TypeAnomalie(
        DOUBLON_APPROCHANT,
        "Même personne à une variation orthographique près",
        "IDENTITE",
        "TB_REF_ASSURES",
        "ASSURE_NOM",
        # Douce : chaque fiche est valide prise isolément. C'est leur
        # rapprochement qui révèle l'anomalie — le cas le plus difficile
        # pour l'outil testé, et le plus fréquent en vrai.
        SEVERITE_DOUCE,
        PORTEE_CAMPAGNE,
    ),
    TypeAnomalie(
        CHAMP_OBLIGATOIRE_VIDE,
        "Champ obligatoire laissé vide",
        "FORMAT",
        "TB_REF_ASSURES",
        "ASSURE_NOM",
        SEVERITE_DURE,
        PORTEE_CAMPAGNE,
    ),
    TypeAnomalie(
        ENCODAGE_CASSE,
        "Caractères cassés à l'import : « N'Guessan » devenu « N?Guessan »",
        "FORMAT",
        "TB_REF_ASSURES",
        "ASSURE_NOM",
        SEVERITE_DOUCE,
        PORTEE_CAMPAGNE,
    ),
    TypeAnomalie(
        FORMAT_DATE_INCOHERENT,
        "Date écrite dans un autre format que la norme du fichier",
        "DATES",
        "TB_FACTURES",
        "FACTURE_DATE_SOINS",
        SEVERITE_DURE,
        PORTEE_CAMPAGNE,
    ),
    TypeAnomalie(
        TENTATIVE_INJECTION,
        "Tentative d'injection glissée dans un champ texte",
        "FORMAT",
        "TB_REF_ASSURES",
        "ASSURE_NOM",
        SEVERITE_DURE,
        PORTEE_CAMPAGNE,
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
    # Chapitre 5 — les trois dimensions qui n'avaient aucun injecteur.
    DOUBLON_EXACT: UNICITE,
    DOUBLON_APPROCHANT: UNICITE,
    CHAMP_OBLIGATOIRE_VIDE: COMPLETUDE,
    ENCODAGE_CASSE: TECHNIQUE,
    # Une injection n'est pas un défaut de saisie : c'est une chaîne
    # délibérément hostile qui a franchi les contrôles. Elle éprouve la même
    # chose que les caractères cassés — ce que l'outil fait d'un texte qu'il
    # n'attendait pas.
    TENTATIVE_INJECTION: TECHNIQUE,
    # Une date au mauvais format reste une question de forme, pas de sens :
    # le 12/03/2025 est une date parfaitement valide, mal écrite.
    FORMAT_DATE_INCOHERENT: VALIDITE,
}


CODES = tuple(type_anomalie.code for type_anomalie in CATALOGUE_INITIAL)

# Ce que le moteur temps réel sait poser, et donc ce que la console
# d'injection a le droit d'afficher. Les types de portée « campagne » en sont
# exclus : le moteur n'a aucune mémoire des passages déjà écrits.
CODES_MOTEUR = tuple(
    type_anomalie.code
    for type_anomalie in CATALOGUE_INITIAL
    if type_anomalie.portee == PORTEE_TOUTES
)
