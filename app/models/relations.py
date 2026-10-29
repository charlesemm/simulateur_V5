"""Relations ORM entre les modèles générés.

`app/models/mirka.py` est généré depuis le schéma de Mirka, et ne contient que
des colonnes. Les relations vivent ici, à la main, pour deux raisons.

La première est que leurs noms ne se déduisent pas du schéma : `provisions`,
`statuses`, `medical_acts` ont été choisis par le code qui les consomme, et une
génération automatique les aurait rebaptisés, cassant les appelants sans
bénéfice.

La seconde est que Mirka ne déclare pas toutes ses clés étrangères :
`TB_FACTURES_PATHOLOGIES`, `TB_FACTURES_STATUTS` et
`TB_ENTENTES_PREALABLES_ACTES_MEDICAUX` se rattachent à leur parent par une
colonne homonyme, sans contrainte en base. SQLAlchemy ne peut donc rien
inférer, et chaque jointure est écrite explicitement.

Les relations sont posées par affectation après la définition des classes, ce
qui laisse le module généré intact à chaque régénération. On n'en déclare que
ce que le code utilise : en ajouter « au cas où » coûterait des jointures que
personne ne demande.

Toutes sont `viewonly` : le code ne s'en sert que pour lire une facture et ses
lignes. Les laisser modifiables donnerait à SQLAlchemy la charge d'une cascade
qu'aucune contrainte de Mirka ne garantit — le moteur écrit ses lignes
lui-même, explicitement, et c'est lui qui doit rester maître de l'ordre.
"""

from __future__ import annotations

from sqlalchemy.orm import relationship

from app.models.mirka import (
    Invoice,
    InvoicePathology,
    InvoicePrescription,
    InvoiceProvision,
    InvoiceStatus,
    PriorAuthorization,
    PriorAuthorizationMedicalAct,
)


def _lignes_de_facture(enfant: type, colonne: str = "FACTURE_NUMERO"):
    """Rend la relation d'une facture vers ses lignes, jointure explicite."""
    return relationship(
        enfant,
        primaryjoin=Invoice.__table__.c[colonne] == enfant.__table__.c[colonne],
        foreign_keys=[enfant.__table__.c[colonne]],
        viewonly=True,
    )


Invoice.provisions = _lignes_de_facture(InvoiceProvision)
Invoice.pathologies = _lignes_de_facture(InvoicePathology)
Invoice.prescriptions = _lignes_de_facture(InvoicePrescription)
Invoice.statuses = _lignes_de_facture(InvoiceStatus)

PriorAuthorization.medical_acts = relationship(
    PriorAuthorizationMedicalAct,
    primaryjoin=(
        PriorAuthorization.__table__.c.ENTENTE_PREALABLE_ID
        == PriorAuthorizationMedicalAct.__table__.c.ENTENTE_PREALABLE_ID
    ),
    foreign_keys=[PriorAuthorizationMedicalAct.__table__.c.ENTENTE_PREALABLE_ID],
    viewonly=True,
)
