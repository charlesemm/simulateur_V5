from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models import Invoice
from api.schema import (
    InvoiceDetailResponse, InvoicePathologySchema, InvoicePrescriptionSchema,
    InvoiceProvisionSchema, InvoiceStatusSchema,
)

router = APIRouter(prefix="/factures", tags=["Factures"])

@router.get("/{facture_numero}", response_model=InvoiceDetailResponse)
async def get_invoice(facture_numero: str) -> InvoiceDetailResponse:
    """Charge la facture et toutes ses collections en nombre fixe de requêtes."""

    async with async_session_factory() as session:
        statement = select(Invoice).where(Invoice.facture_numero == facture_numero).options(
            selectinload(Invoice.pathologies), selectinload(Invoice.prescriptions),
            selectinload(Invoice.provisions), selectinload(Invoice.statuses),
        )
        invoice = (await session.execute(statement)).scalar_one_or_none()
        if invoice is None:
            raise HTTPException(status_code=404, detail="Facture introuvable.")
        return InvoiceDetailResponse(
            facture_numero=invoice.facture_numero, personne_uuid=invoice.personne_uuid,
            centre_sante_code=invoice.centre_sante_code,
            type_facture_code=invoice.type_facture_code,
            facture_date_soins=invoice.facture_date_soins,
            dossier_numero=invoice.dossier_numero,
            entente_prealable_id=invoice.entente_prealable_id,
            pathologies=[InvoicePathologySchema(code=row.pathologie_code, date_debut=row.pathologie_date_debut, observations=row.pathologie_observations) for row in invoice.pathologies],
            prescriptions=[InvoicePrescriptionSchema(code=row.prescription_code, date_debut=row.date_debut, quantite=row.prescription_quantite, posologie=row.prescription_posologie, duree=row.prescription_duree) for row in invoice.prescriptions],
            prestations=[InvoiceProvisionSchema(code=row.prestation_code, professionnel_sante_code=row.professionnel_sante_code, statut_remboursement=row.statut_remboursement, prix_unitaire=row.prestation_prix_unitaire, montant_depense=row.prestation_montant_depense, montant_assure=row.prestation_montant_assure) for row in invoice.provisions],
            statuts=[InvoiceStatusSchema(code=row.statut_code, date_debut=row.statut_date_debut, observations=row.statut_observations) for row in invoice.statuses],
        )