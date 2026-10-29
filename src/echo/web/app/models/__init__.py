"""Expose tous les modèles pour la découverte complète des métadonnées.

Les modèles métier sont désormais générés depuis le schéma de Mirka
(`app/models/mirka.py`). Les trois modules qui les portaient à la main —
`schema.py`, `assures.py`, `referentiels.py` — ont disparu : leurs classes
vivent ici sous les mêmes noms, ce qui a épargné aux vingt modules
importateurs de changer d'import.

`Pharmacie` n'est plus exporté : Mirka n'a pas de table des pharmacies, une
pharmacie y étant un centre de santé d'un type donné. Voir
`app/models/correspondances.py`.
"""

from echo.web.app.models.base import AuditMixin, Base, SimulationScopedMixin
from echo.web.app.models.mirka import (
    Agent,
    CareBasket,
    CareNetwork,
    CenterHealthAgent,
    Collectivite,
    CollectiviteAddress,
    Country,
    Dci,
    Department,
    HealthCenter,
    HealthProfessional,
    HealthProfessionalCenter,
    HealthProfessionalMedicalSpecialty,
    InsuredBirthInfo,
    InsuredEntitlement,
    InsuredIdentifier,
    InsuredPerson,
    InsuredProfession,
    InsuredRight,
    Invoice,
    InvoiceHealthProfessional,
    InvoicePathology,
    InvoicePrescription,
    InvoiceProvision,
    InvoiceRejection,
    InvoiceStatus,
    Locality,
    MedicalAct,
    MedicalSpecialty,
    Medication,
    NetworkMedicalAct,
    Pathology,
    PriorAuthorization,
    PriorAuthorizationMedicalAct,
    PriorAuthorizationProvision,
    PriorAuthorizationStatus,
    Product,
    ProductRegime,
    Regime,
    Region,
    TypeInvoice,
)

# Importé pour son effet : le module attache les relations aux classes
# générées. Sans cet import, `Invoice.provisions` n'existe pas.
from echo.web.app.models import relations as _relations  # noqa: E402,F401

__all__ = [name for name in globals() if not name.startswith("_")]
