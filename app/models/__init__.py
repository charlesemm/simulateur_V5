"""Expose tous les modèles pour la découverte complète des métadonnées."""

from app.models.base import Base
from app.models.assures import (
    InsuredBirthInfo,
    InsuredIdentifier,
    InsuredProfession,
    InsuredRight,
)
from app.models.referentiels import Country, Department, Locality, Regime, Region
from app.models.schema import (
    Agent,
    CenterHealthAgent,
    HealthCenter,
    HealthProfessional,
    HealthProfessionalCenter,
    HealthProfessionalMedicalSpecialty,
    InsuredPerson,
    Invoice,
    InvoicePathology,
    InvoicePrescription,
    InvoiceProvision,
    InvoiceRejection,
    InvoiceStatus,
    MedicalAct,
    MedicalSpecialty,
    Medication,
    Pathology,
    PriorAuthorization,
    PriorAuthorizationMedicalAct,
    PriorAuthorizationProvision,
    PriorAuthorizationStatus,
    TypeInvoice,
)

__all__ = [name for name in globals() if not name.startswith("_")]
