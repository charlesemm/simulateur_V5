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
    """Paramètre le démarrage continu du moteur."""

    vitesse: float = Field(default=60, gt=0, le=86400)
    nombre_passages_simultanes_max: int = Field(default=20, ge=1, le=200)


class SimulationSpeedRequest(ApiModel):
    """Modifie la vitesse d'un moteur déjà démarré."""

    vitesse: float = Field(gt=0, le=86400)


class SimulationStatusResponse(ApiModel):
    """Expose l'état observable du moteur."""

    etat: str
    vitesse: float
    passages_actifs: int
    passages_simultanes_max: int


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
    prix_unitaire: Decimal | None
    montant_depense: Decimal | None
    montant_assure: Decimal | None


class InvoiceStatusSchema(ApiModel):
    code: str
    date_debut: date
    observations: str | None


class InvoiceDetailResponse(ApiModel):
    facture_numero: str
    personne_uuid: UUID
    centre_sante_code: str
    type_facture_code: str
    facture_date_soins: date
    dossier_numero: str
    entente_prealable_id: int | None
    pathologies: list[InvoicePathologySchema]
    prescriptions: list[InvoicePrescriptionSchema]
    prestations: list[InvoiceProvisionSchema]
    statuts: list[InvoiceStatusSchema]


class HealthCenterSchema(ApiModel):
    centre_sante_code: str
    denomination: str
    type_code: str | None
    numero_immatriculation: str


class HealthCenterListResponse(ApiModel):
    total: int
    centres: list[HealthCenterSchema]