"""T4 — Catalogue de métadonnées et lignage des données d'ÉCHO.

Ce que la gouvernance réclame d'abord n'est pas un tableau de bord mais un
inventaire : quelles données existent, qui en répond, lesquelles sont
personnelles, et d'où elles viennent.

Le catalogue est déclaré ici plutôt que déduit du schéma : le propriétaire
d'une donnée et sa criticité ne s'inventent pas à la lecture des colonnes.
"""

from __future__ import annotations

from dataclasses import dataclass

# Domaines fonctionnels du dispositif CMU.
ASSURE = "Assuré"
OFFRE_SOINS = "Offre de soins"
FACTURATION = "Facturation"
PILOTAGE = "Pilotage"

CRITIQUE = "critique"
IMPORTANTE = "importante"
COURANTE = "courante"


@dataclass(frozen=True, slots=True)
class FicheTable:
    """La fiche de gouvernance d'une table."""

    table: str
    domaine: str
    description: str
    proprietaire: str
    criticite: str
    donnees_personnelles: bool


CATALOGUE: tuple[FicheTable, ...] = (
    FicheTable("TB_REF_ASSURES", ASSURE,
               "Identité civile des assurés du dispositif",
               "Direction des affiliations", CRITIQUE, True),
    FicheTable("TB_ASSURES_DROITS", ASSURE,
               "Ouverture et fermeture des droits, mois par mois",
               "Direction des affiliations", CRITIQUE, True),
    FicheTable("TB_ASSURES_IDENTIFIANTS", ASSURE,
               "Identifiants rattachés à l'assuré, historisés",
               "Direction des affiliations", CRITIQUE, True),
    FicheTable("TB_ASSURES_PROFESSIONS", ASSURE,
               "Professions successives, qui déterminent le régime",
               "Direction des affiliations", IMPORTANTE, True),
    FicheTable("TB_ASSURES_INFOS_NAISSANCE", ASSURE,
               "Lieu et pays de naissance, historisés",
               "Direction des affiliations", COURANTE, True),
    FicheTable("TB_REF_CENTRES_SANTE", OFFRE_SOINS,
               "Centres de santé conventionnés",
               "Direction de l'offre de soins", IMPORTANTE, False),
    FicheTable("TB_REF_PROFESSIONNELS_SANTE", OFFRE_SOINS,
               "Professionnels de santé et leurs spécialités",
               "Direction de l'offre de soins", IMPORTANTE, True),
    FicheTable("TB_REF_AGENTS", OFFRE_SOINS,
               "Agents CNAM, dont les médecins conseils",
               "Direction des ressources humaines", COURANTE, True),
    FicheTable("TB_FACTURES", FACTURATION,
               "Facture centrale d'un parcours de soins",
               "Direction des prestations", CRITIQUE, True),
    FicheTable("TB_FACTURES_PRESTATIONS", FACTURATION,
               "Détail des prestations et de leur remboursement",
               "Direction des prestations", CRITIQUE, False),
    FicheTable("TB_FACTURES_PATHOLOGIES", FACTURATION,
               "Pathologies rattachées à une facture",
               "Direction médicale", CRITIQUE, True),
    FicheTable("TB_FACTURES_PRESCRIPTIONS", FACTURATION,
               "Médicaments prescrits sur une facture",
               "Direction médicale", IMPORTANTE, True),
    FicheTable("TB_ENTENTES_PREALABLES", FACTURATION,
               "Demandes d'accord préalable et leur décision",
               "Direction médicale", CRITIQUE, True),
    FicheTable("TB_SIMULATIONS", PILOTAGE,
               "Exécutions du simulateur et leurs paramètres",
               "Service données", COURANTE, False),
    FicheTable("TB_ANOMALIES_INJECTIONS", PILOTAGE,
               "Vérité terrain des anomalies injectées",
               "Service données", IMPORTANTE, False),
    FicheTable("TB_MDM_PAIRES", PILOTAGE,
               "Vérité terrain du rapprochement d'identités",
               "Service données", IMPORTANTE, False),
    FicheTable("TB_REFUS_ACCUEIL", ASSURE,
               "Présentations refusées à l'accueil, faute de droits ouverts",
               "Direction des affiliations", IMPORTANTE, True),
    FicheTable("TB_EVENEMENTS_METIER", PILOTAGE,
               "Journal des événements produits par le moteur",
               "Service données", COURANTE, False),
)


@dataclass(frozen=True, slots=True)
class Lien:
    """Un flux entre deux tables, et le traitement qui l'alimente."""

    source: str
    cible: str
    traitement: str


# Lignage réel du simulateur : ce que chaque traitement alimente à partir de
# quoi. Il est déclaré à partir du code qui écrit, pas d'un schéma supposé.
LIGNAGE: tuple[Lien, ...] = (
    Lien("seed/runner.py", "TB_REF_ASSURES", "Peuplement du référentiel"),
    Lien("seed/runner.py", "TB_ASSURES_DROITS", "Peuplement du référentiel"),
    Lien("seed/runner.py", "TB_REF_CENTRES_SANTE", "Peuplement du référentiel"),
    Lien("seed/runner.py", "TB_REF_AGENTS", "Peuplement du référentiel"),
    Lien("TB_REF_ASSURES", "TB_FACTURES", "Moteur de passage"),
    Lien("TB_ASSURES_DROITS", "TB_FACTURES", "Contrôle des droits à l'accueil"),
    Lien("TB_ASSURES_DROITS", "TB_REFUS_ACCUEIL", "Contrôle des droits à l'accueil"),
    Lien("TB_TV_REGIMES", "TB_FACTURES", "Régime et taux de l'assuré"),
    Lien("TB_FACTURES", "TB_FACTURES_PRESTATIONS", "Moteur de passage"),
    Lien("TB_FACTURES", "TB_FACTURES_PATHOLOGIES", "Moteur de passage"),
    Lien("TB_FACTURES", "TB_ENTENTES_PREALABLES", "Moteur de passage"),
    Lien("TB_FACTURES", "TB_EVENEMENTS_METIER", "Bus d'événements"),
    Lien("TB_REF_ANOMALIES", "TB_ANOMALIES_INJECTIONS", "Injecteurs d'anomalies"),
    Lien("TB_REF_ASSURES", "TB_MDM_PAIRES", "Générateur d'identités jumelles"),
    Lien("TB_SIMULATIONS", "TB_FACTURES", "Rattachement à l'exécution"),
)
