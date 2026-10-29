"""Correspondance entre les modèles du simulateur et les tables de Mirka.

Le simulateur portait un schéma métier écrit à la main. Il porte désormais
celui de Mirka, préfixé `TB_SIM_`. Les **noms de classes sont conservés** :
`Invoice` reste `Invoice`, et les vingt modules qui l'importent n'ont pas à
changer d'import. Seules la table visée et ses colonnes changent.

Ce fichier est la seule source de cette correspondance. Les modèles de
`app/models/mirka.py` en sont générés par `tools/generer_modeles_orm.py` :
corriger une ligne ici et régénérer suffit, il n'y a pas de second endroit à
mettre à jour.

Vingt-huit des trente-quatre tables se retrouvent chez Mirka sous le même nom,
au préfixe près. Les six autres ont demandé une décision, consignée ci-dessous.
"""

from __future__ import annotations

# Nom de classe -> table de Mirka (sans le préfixe TB_SIM_, ajouté à la lecture).
#
# Les six décisions, et leur raison :
#
# - `InsuredPerson` -> `ASSURES`. Mirka distingue le registre des assurés
#   (`TB_ASSURES`) de la chaîne d'enrôlement (`TB_ENROLEMENT_PERSONNES`, ses
#   photos, ses empreintes, ses motifs de recyclage). L'ancien
#   `TB_REF_ASSURES` était un registre : il devient `ASSURES`. Le parcours
#   d'inscription (`simulation/inscription.py`) relève, lui, de
#   `ENROLEMENT_PERSONNES`.
# - `Agent` -> `AGENTS`. Mirka ne préfixe pas cette table `REF_`.
# - `Dci` -> `REF_MEDICAMENTS_DCI`. La dénomination commune internationale est
#   rattachée au référentiel des médicaments chez Mirka.
# - `MedicalSpecialty` -> `TV_SPECIALITES_MEDICALES`. C'est une table de
#   valeurs chez Mirka, pas un référentiel.
# - `HealthProfessionalCenter` -> `CENTRES_SANTE_PROFESSIONNELS_SANTE`. Même
#   table d'association, nommée dans l'autre sens.
# - `Pharmacie` : **supprimé**. Mirka n'a pas de table des pharmacies : une
#   pharmacie y est un centre de santé d'un type donné. Le modèle disparaît
#   donc, et le code qui l'utilisait doit filtrer `HealthCenter` sur son type
#   d'établissement. Voir PHARMACIE_SUPPRIMEE plus bas.
CORRESPONDANCES: dict[str, str] = {
    # Registre des assurés et ses satellites
    "InsuredPerson": "ASSURES",
    "InsuredRight": "ASSURES_DROITS",
    "InsuredIdentifier": "ASSURES_IDENTIFIANTS",
    "InsuredBirthInfo": "ASSURES_INFOS_NAISSANCE",
    "InsuredProfession": "ASSURES_PROFESSIONS",
    # Offre de soins
    "HealthCenter": "REF_CENTRES_SANTE",
    "Collectivite": "REF_COLLECTIVITES",
    # Mirka ne porte pas de coordonnees sur la collectivite elle-meme : une
    # position est un attribut d'adresse.
    "CollectiviteAddress": "REF_COLLECTIVITES_ADRESSES",
    "Agent": "AGENTS",
    "CenterHealthAgent": "CENTRES_SANTE_AGENTS",
    "HealthProfessional": "REF_PROFESSIONNELS_SANTE",
    "MedicalSpecialty": "TV_SPECIALITES_MEDICALES",
    "HealthProfessionalMedicalSpecialty": "REF_PROFESSIONNELS_SANTE_SPECIALITES_MEDICALES",
    "HealthProfessionalCenter": "CENTRES_SANTE_PROFESSIONNELS_SANTE",
    # Nomenclatures de soins
    "Pathology": "REF_PATHOLOGIES",
    "Medication": "REF_MEDICAMENTS",
    "Dci": "REF_MEDICAMENTS_DCI",
    "MedicalAct": "REF_ACTES_MEDICAUX",
    # Factures
    "TypeInvoice": "TV_TYPES_FACTURES",
    "Invoice": "FACTURES",
    "InvoicePathology": "FACTURES_PATHOLOGIES",
    "InvoicePrescription": "FACTURES_PRESCRIPTIONS",
    "InvoiceProvision": "FACTURES_PRESTATIONS",
    "InvoiceRejection": "FACTURES_REJETS",
    "InvoiceStatus": "FACTURES_STATUTS",
    # Ententes préalables
    "PriorAuthorization": "ENTENTES_PREALABLES",
    "PriorAuthorizationStatus": "ENTENTES_PREALABLES_STATUTS",
    "PriorAuthorizationMedicalAct": "ENTENTES_PREALABLES_ACTES_MEDICAUX",
    "PriorAuthorizationProvision": "ENTENTES_PREALABLES_PRESTATIONS",
    # Droits et produits. Mirka ne porte pas le régime sur l'assuré : le chemin
    # est assuré -> TB_DROITS (son produit) -> TB_PRODUITS_REGIMES -> régime.
    "InsuredEntitlement": "DROITS",
    "Product": "PRODUITS",
    "ProductRegime": "PRODUITS_REGIMES",
    # Le reseau de soins ne tient pas seul : il appartient a un panier, qui
    # appartient a un produit. Semer les tarifs sans cette chaine laisserait
    # des lignes rattachees a un reseau inexistant.
    "CareBasket": "PANIERS_SOINS",
    "CareNetwork": "RESEAUX_SOINS",
    # Le tarif n'est pas une propriété de l'acte chez Mirka, mais du réseau de
    # soins qui le rembourse.
    "NetworkMedicalAct": "RESEAUX_SOINS_ACTES_MEDICAUX",
    # Mirka rattache le praticien à la facture, pas à chacune de ses lignes.
    "InvoiceHealthProfessional": "FACTURES_PROFESSIONNELS_SANTE",
    # Localisation et régimes
    "Country": "TV_LOCALISATION_PAYS",
    "Region": "TV_LOCALISATION_REGIONS",
    "Department": "TV_LOCALISATION_DEPARTEMENTS",
    "Locality": "TV_LOCALISATION_LOCALITES",
    "Regime": "TV_REGIMES",
}

# Le modèle `Pharmacie` n'a pas d'équivalent : il est supprimé plutôt que mappé
# sur la même table que `HealthCenter`, ce qui aurait donné deux classes pour
# une table et autant d'ambiguïtés de requête.
PHARMACIE_SUPPRIMEE = (
    "Mirka n'a pas de table des pharmacies : une pharmacie est un centre de "
    "santé dont le type d'établissement sanitaire la désigne comme telle. "
    "Remplacer `Pharmacie` par `HealthCenter` filtré sur "
    "TYPE_ETABLISSEMENT_SANITAIRE_CODE."
)

# Clés déclarées pour l'ORM seul, sur les tables où Mirka n'a pas posé de clé
# primaire. SQLAlchemy exige une identité pour mapper une classe ; la base, elle,
# reste fidèle à Mirka et ne reçoit aucune contrainte supplémentaire.
CLES_LOGIQUES: dict[str, list[str]] = {
    "NetworkMedicalAct": [
        "RESEAU_CODE",
        "ACTE_MEDICAL_CODE",
        "RESEAU_ACTE_MEDICAL_DATE_DEBUT",
    ],
}

PREFIXE = "TB_SIM_"


def table_de(classe: str) -> str:
    """Rend le nom complet de la table visée par un modèle."""
    return PREFIXE + CORRESPONDANCES[classe]
