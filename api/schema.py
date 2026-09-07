"""Déclare tous les contrats d'entrée et de sortie de l'API CMU."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base stricte commune aux réponses de l'API."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class MessageResponse(ApiModel):
    """Confirme une opération ne retournant pas de ressource."""

    message: str


class HealthResponse(ApiModel):
    """Confirme la disponibilité du processus ASGI."""

    statut: str


class SimulationStartRequest(ApiModel):
    """Paramètre le démarrage continu du moteur.

    Tout est facultatif : ce qui manque vient du profil du type demandé. Les
    réglages d'anomalies et d'aléas ne valent que pour cette exécution ; le
    catalogue en base reste ce que l'opérateur y a mis.
    """

    type_simulation: str | None = None
    libelle: str | None = Field(default=None, max_length=150)
    vitesse: float | None = Field(default=None, gt=0, le=86400)
    nombre_passages_simultanes_max: int | None = Field(default=None, ge=1, le=200)
    # Durée que l'opérateur vise, en minutes. Elle ne pilote pas le moteur —
    # rien ne l'arrête à l'échéance — mais elle donne au poste de pilotage le
    # repère qui lui manquait : sans objectif, aucune progression n'a de sens.
    duree_visee_minutes: int | None = Field(default=None, ge=1, le=1440)
    # Par code d'anomalie : {"taux": 0.15, "declenchement": "continu", ...}
    anomalies: dict[str, dict[str, Any]] | None = None
    # Par code d'aléa : {"probabilite": 0.05, "taille": 50, ...}
    aleas: dict[str, dict[str, Any]] | None = None


class SimulationSpeedRequest(ApiModel):
    """Modifie la vitesse d'un moteur déjà démarré."""

    vitesse: float = Field(gt=0, le=86400)


class SimulationStatusResponse(ApiModel):
    """Expose l'état observable du moteur."""

    etat: str
    vitesse: float
    passages_actifs: int
    passages_simultanes_max: int
    # Nul tant qu'aucune exécution n'a été ouverte, ou après son arrêt.
    simulation_id: UUID | None = None
    type_simulation: str | None = None
    # Passages coupés volontairement par un aléa, à ne pas confondre avec des
    # échecs du simulateur.
    passages_interrompus: int = 0


class SimulationRunResponse(ApiModel):
    """Décrit une exécution enregistrée du moteur."""

    simulation_id: UUID
    simulation_libelle: str
    simulation_statut: str
    simulation_parametres: dict[str, Any]
    simulation_date_debut: datetime
    simulation_date_fin: datetime | None = None
    utilisateur_uuid: UUID | None = None
    passages_reussis: int
    passages_echoues: int
    simulation_type: str | None = None


class ProfilResponse(ApiModel):
    """Décrit un type de simulation et son réglage."""

    code: str
    libelle: str
    description: str
    couleur: str
    vitesse: float
    passages_simultanes_max: int
    anomalies: dict[str, Any]
    aleas: dict[str, Any]
    # Le serveur dit lui-même ce qui est ouvert et où cela mène. L'écran
    # d'accueil grisait les types dans son propre code : chaque ouverture
    # demandait alors de retoucher le navigateur.
    disponible: bool
    parcours: str | None


class PalierResponse(ApiModel):
    """Un palier de charge du banc d'essai."""

    code: str
    libelle: str
    volume_propose: int
    description: str


class FormatExportResponse(ApiModel):
    """Un format de téléchargement du jeu d'une campagne (M4)."""

    code: str
    libelle: str
    extension: str
    description: str


class DimensionResponse(ApiModel):
    """Une des huit dimensions de qualité du cahier des charges."""

    code: str
    libelle: str
    description: str
    # Nombre de types d'anomalies capables de l'éprouver aujourd'hui. Zéro
    # signifie que la dimension est décrite mais pas encore injectable.
    types_disponibles: int


class TypeAnomalieCampagneResponse(ApiModel):
    """Un type d'anomalie tel qu'une campagne le propose.

    Servi depuis le catalogue en code, et non depuis la table : une campagne
    porte ses propres taux, le réglage de la console d'injection ne la
    concerne pas.
    """

    code: str
    libelle: str
    famille: str
    couleur: str
    dimension: str
    dimension_libelle: str
    table_cible: str
    colonne_cible: str
    severite: str


class ReglageAnomalieCampagne(ApiModel):
    """Le taux d'un type d'anomalie pour une campagne donnée."""

    # Le taux est une part entre 0 et 1 ; l'écran le saisit en pourcentage et
    # le convertit. Un taux nul est refusé : activer un type sans en injecter
    # aucun produirait une ligne de score toujours vide.
    taux: float = Field(gt=0.0, le=1.0)


class ProchaineReferenceResponse(ApiModel):
    """La référence que porterait la prochaine campagne, sans la réserver."""

    reference: str


class CampagneCreateRequest(ApiModel):
    """Ouvre une campagne de test.

    Tout est facultatif : le libellé n'est plus saisi — il découle de la
    référence incrémentielle attribuée par le serveur —, sans volume celui
    que propose le palier, et sans graine une graine tirée — que la réponse
    renvoie, car c'est elle qui rend la campagne rejouable.
    """

    palier: str | None = None
    volume_cible: int | None = Field(default=None, ge=100, le=5_000_000)
    graine: int | None = Field(default=None, ge=1, le=2_147_483_647)
    # Les types retenus et leur taux. Un type absent ne sera pas injecté :
    # l'écran envoie exactement ce qu'il affiche, jamais un réglage implicite.
    anomalies: dict[str, ReglageAnomalieCampagne] | None = None


class CampagneResponse(ApiModel):
    """Une campagne de test et son état."""

    campagne_id: UUID
    campagne_reference: str
    campagne_libelle: str
    campagne_statut: str
    campagne_graine: int
    campagne_palier: str
    campagne_volume_cible: int
    campagne_parametres: dict[str, Any]
    date_creation: datetime
    campagne_date_fin: datetime | None
    # Ce que la génération a laissé. Nuls tant qu'elle n'a pas eu lieu.
    campagne_date_generation: datetime | None = None
    campagne_lignes_generees: int = 0
    campagne_anomalies_posees: int = 0
    campagne_empreinte: str | None = None
    campagne_fichier: str | None = None


class ProgressionResponse(ApiModel):
    """Où en est la génération d'un jeu de campagne."""

    statut: str
    volume_cible: int
    lignes_generees: int
    anomalies_posees: int
    pourcentage: float
    terminee: bool
    # Renseignée quand la génération s'est interrompue : la campagne repasse
    # alors à « créée », un jeu à moitié produit n'ayant aucune valeur.
    erreur: str | None = None


class LigneCorrigeResponse(ApiModel):
    """Une anomalie posée, telle que le corrigé la consigne."""

    corrige_ligne: int
    corrige_champ: str
    anomalie_code: str
    corrige_valeur_origine: str
    corrige_valeur_injectee: str


class CorrigeResponse(ApiModel):
    """Un extrait du corrigé, et le compte complet par type."""

    campagne_id: UUID
    total: int
    par_anomalie: dict[str, int]
    lignes: list[LigneCorrigeResponse]


class CadenceResponse(ApiModel):
    """Ce qu'il faut pour projeter un volume avant de lancer le moteur.

    L'écran de lancement ne peut pas deviner le rythme d'arrivée : il est
    tiré d'une loi exponentielle dont la moyenne vit dans la configuration
    du moteur. On la sert telle quelle plutôt que de la recopier dans le
    navigateur, où elle dériverait à la première retouche.
    """

    passage_arrival_mean_seconds: float
    vitesse_par_defaut: float
    passages_simultanes_max: int


class CommandeRequest(ApiModel):
    """Ordre adressé à un moteur déjà lancé."""

    ordre: str
    cible: str


class ExecutionDetailResponse(ApiModel):
    """Une exécution et le compte de ce qu'elle a laissé en base."""

    execution: SimulationRunResponse
    volumetrie: dict[str, int]
    anomalies_par_type: dict[str, int]


class WindowSchema(ApiModel):
    hours: int
    from_: datetime = Field(alias="from", serialization_alias="from")
    to: datetime


class PassagesKpiSchema(ApiModel):
    en_cours: int
    clotures: int
    total: int


class ActDistributionSchema(ApiModel):
    type: str
    nombre: int
    pourcentage: float


class AgreementRateSchema(ApiModel):
    nombre: int
    pourcentage: float


class AgreementDelaySchema(ApiModel):
    medecin_conseil: float | None
    validation_office: float | None


class AgreementsKpiSchema(ApiModel):
    global_: dict[str, AgreementRateSchema] = Field(alias="global", serialization_alias="global")
    par_centre: dict[str, dict[str, int]]
    delai_moyen_secondes: AgreementDelaySchema


class AmountPairSchema(ApiModel):
    cmu: float
    assure: float


class AmountsKpiSchema(ApiModel):
    cumule: AmountPairSchema
    par_centre: dict[str, AmountPairSchema]


class PathologyTopSchema(ApiModel):
    code: str
    libelle: str
    nombre: int


class CenterLoadSchema(ApiModel):
    centre_sante_code: str
    passages_actifs: int


class KpiSnapshotResponse(ApiModel):
    """Représente le snapshot complet partagé avec Socket.IO."""

    generated_at: datetime
    window: WindowSchema
    passages: PassagesKpiSchema
    actes_repartition: list[ActDistributionSchema]
    ententes: AgreementsKpiSchema
    montants: AmountsKpiSchema
    top_pathologies: list[PathologyTopSchema]
    charge_centres: list[CenterLoadSchema]


class KpiName(str, Enum):
    passages = "passages"
    ententes_acceptees = "ententes_acceptees"
    montant_cmu = "montant_cmu"
    montant_assure = "montant_assure"


class Granularity(str, Enum):
    minute = "minute"
    heure = "heure"
    jour = "jour"


class HistoryPointSchema(ApiModel):
    timestamp: datetime
    value: float


class KpiHistoryResponse(ApiModel):
    kpi_name: KpiName
    granularite: Granularity
    since: datetime
    points: list[HistoryPointSchema]


class InvoicePathologySchema(ApiModel):
    code: str
    date_debut: date
    observations: str | None


class InvoicePrescriptionSchema(ApiModel):
    code: str
    date_debut: date
    quantite: Decimal | None
    posologie: str | None
    duree: int | None


class InvoiceProvisionSchema(ApiModel):
    code: str
    professionnel_sante_code: str
    statut_remboursement: str | None
    taux_remboursement: Decimal | None
    quantite_prescrite: Decimal | None
    quantite_servie: Decimal | None
    prix_unitaire: Decimal | None
    montant_depense: Decimal | None
    montant_rembourse: Decimal | None
    montant_assure: Decimal | None


class InvoiceStatusSchema(ApiModel):
    code: str
    date_debut: date
    observations: str | None


class InsuredSummarySchema(ApiModel):
    """L'assuré tel qu'il se présente sur la facture, à la date des soins."""

    personne_uuid: UUID
    numero_secu: str
    civilite_code: str | None
    nom: str
    prenoms: str | None
    date_naissance: date | None
    regime_code: str | None
    regime_libelle: str | None
    regime_taux: Decimal | None
    profession_code: str | None
    droits_ouverts: bool | None
    lieu_naissance: str | None
    pays_naissance_code: str | None


class HealthCenterSummarySchema(ApiModel):
    """Le centre où les soins ont été délivrés."""

    centre_sante_code: str
    denomination: str | None
    type_code: str | None
    type_libelle: str | None


class PriorAuthorizationActSchema(ApiModel):
    acte_medical_code: str
    professionnel_sante_code: str | None
    statut: str | None
    taux_remboursement: Decimal | None
    montant_cmu: Decimal | None
    montant_assure: Decimal | None
    motif_rejet: str | None


class PriorAuthorizationSchema(ApiModel):
    entente_prealable_id: int
    entente_prealable_numero: str | None
    type_demande_code: str | None
    type_hospitalisation_code: str | None
    date_debut: date | None
    actes: list[PriorAuthorizationActSchema]


class InvoiceTotalsSchema(ApiModel):
    """Ce que la facture coûte, et qui paie quoi."""

    montant_depense: Decimal
    montant_rembourse: Decimal
    montant_assure: Decimal
    montant_cmu_ententes: Decimal


class InvoiceDetailResponse(ApiModel):
    facture_numero: str
    personne_uuid: UUID
    centre_sante_code: str
    type_facture_code: str
    facture_date_soins: date
    dossier_numero: str | None
    produit_code: str | None
    regime_code: str | None
    regime_taux: Decimal | None
    organisme_code: str | None
    entente_prealable_id: int | None
    passage_id: str | None
    statut_courant: str | None
    assure: InsuredSummarySchema
    centre: HealthCenterSummarySchema
    totaux: InvoiceTotalsSchema
    entente_prealable: PriorAuthorizationSchema | None
    pathologies: list[InvoicePathologySchema]
    prescriptions: list[InvoicePrescriptionSchema]
    prestations: list[InvoiceProvisionSchema]
    statuts: list[InvoiceStatusSchema]


class InvoiceListItemSchema(ApiModel):
    """Une ligne du tableau des factures : l'essentiel du parcours."""

    facture_numero: str
    facture_date_soins: date
    type_facture_code: str
    centre_sante_code: str
    centre_denomination: str | None
    personne_uuid: UUID
    assure_nom_complet: str
    numero_secu: str
    regime_code: str | None
    regime_taux: Decimal | None
    statut_courant: str | None
    entente_prealable_id: int | None
    montant_depense: Decimal
    montant_rembourse: Decimal
    montant_assure: Decimal


class InvoiceListResponse(ApiModel):
    total: int
    limite: int
    decalage: int
    factures: list[InvoiceListItemSchema]


class ParcoursEtapeSchema(ApiModel):
    """Une étape franchie par la facture, telle que le journal l'a vue."""

    ordre: int
    type_evenement: str
    libelle: str
    simulated_at: datetime
    payload: dict[str, Any]


class ParcoursResponse(ApiModel):
    """Le parcours complet d'un passage, reconstitué depuis le journal."""

    passage_id: str
    facture_numero: str | None
    debut: datetime
    fin: datetime
    duree_simulee_secondes: float
    nombre_etapes: int
    etapes: list[ParcoursEtapeSchema]


class HealthCenterSchema(ApiModel):
    centre_sante_code: str
    denomination: str
    type_code: str | None
    numero_immatriculation: str


class HealthCenterListResponse(ApiModel):
    total: int
    centres: list[HealthCenterSchema]