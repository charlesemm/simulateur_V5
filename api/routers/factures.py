"""Consultation des factures : liste filtrable, détail complet et parcours."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import (
    HealthCenter, InsuredBirthInfo, InsuredPerson, InsuredProfession,
    InsuredRight, Invoice, InvoiceProvision, InvoiceStatus,
    PriorAuthorization, Regime,
)
from api.schema import (
    HealthCenterSummarySchema, InsuredSummarySchema, InvoiceDetailResponse,
    InvoiceListItemSchema, InvoiceListResponse, InvoicePathologySchema,
    InvoicePrescriptionSchema, InvoiceProvisionSchema, InvoiceStatusSchema,
    InvoiceTotalsSchema, ParcoursResponse, PriorAuthorizationActSchema,
    PriorAuthorizationSchema,
)
from api.services.parcours import build_parcours, find_passage_id
from auth.dependencies import require_role

# Les factures portent des données de santé : aucun accès anonyme.
router = APIRouter(
    prefix="/factures",
    tags=["Factures"],
    dependencies=[Depends(require_role("observateur"))],
)

ZERO = Decimal("0")


def _appliquer_filtres(
    requete: Select,
    centre_sante_code: str | None,
    regime_code: str | None,
    type_facture_code: str | None,
    date_min: date | None,
    date_max: date | None,
) -> Select:
    """Ajoute à la requête les seuls filtres réellement fournis."""

    if centre_sante_code:
        requete = requete.where(Invoice.centre_sante_code == centre_sante_code)
    if regime_code:
        requete = requete.where(Invoice.regime_code == regime_code)
    if type_facture_code:
        requete = requete.where(Invoice.type_facture_code == type_facture_code)
    if date_min:
        requete = requete.where(Invoice.facture_date_soins >= date_min)
    if date_max:
        requete = requete.where(Invoice.facture_date_soins <= date_max)
    return requete


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    centre_sante_code: str | None = None,
    regime_code: str | None = None,
    type_facture_code: str | None = None,
    date_min: date | None = None,
    date_max: date | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
) -> InvoiceListResponse:
    """Liste les factures les plus récentes, filtrées et paginées.

    Trois requêtes suffisent quelle que soit la page : la page elle-même, puis
    les montants et le statut courant des seules factures affichées. Les
    identifiants passés en paramètre restent donc bornés par `limite`, loin
    de la limite asyncpg de 32 767 paramètres.
    """

    async with async_session_factory() as session:
        base = _appliquer_filtres(
            select(Invoice), centre_sante_code, regime_code,
            type_facture_code, date_min, date_max,
        )
        total = (await session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()

        lignes = list((await session.execute(
            base.add_columns(InsuredPerson, HealthCenter)
            .join(InsuredPerson, Invoice.personne_uuid == InsuredPerson.personne_uuid)
            .join(HealthCenter, Invoice.centre_sante_code == HealthCenter.centre_sante_code)
            .order_by(Invoice.facture_date_soins.desc(), Invoice.facture_numero.desc())
            .offset(decalage).limit(limite)
        )).all())

        numeros = [ligne[0].facture_numero for ligne in lignes]
        montants = await _charger_montants(session, numeros)
        statuts = await _charger_statuts_courants(session, numeros)

    return InvoiceListResponse(
        total=total, limite=limite, decalage=decalage,
        factures=[
            InvoiceListItemSchema(
                facture_numero=facture.facture_numero,
                facture_date_soins=facture.facture_date_soins,
                type_facture_code=facture.type_facture_code,
                centre_sante_code=facture.centre_sante_code,
                centre_denomination=centre.centre_sante_denomination,
                personne_uuid=facture.personne_uuid,
                assure_nom_complet=_nom_complet(assure),
                numero_secu=assure.numero_secu,
                regime_code=facture.regime_code,
                regime_taux=facture.regime_taux,
                statut_courant=statuts.get(facture.facture_numero),
                entente_prealable_id=facture.entente_prealable_id,
                **montants.get(facture.facture_numero, _montants_vides()),
            )
            for facture, assure, centre in lignes
        ],
    )


def _nom_complet(assure: InsuredPerson) -> str:
    """Assemble nom et prénoms en une seule chaîne affichable."""

    return f"{assure.assure_nom} {assure.assure_prenoms or ''}".strip()


def _montants_vides() -> dict[str, Decimal]:
    """Montants d'une facture sans aucune prestation."""

    return {"montant_depense": ZERO, "montant_rembourse": ZERO, "montant_assure": ZERO}


async def _charger_montants(session, numeros: list[str]) -> dict[str, dict[str, Decimal]]:
    """Agrège les montants des prestations, facture par facture."""

    if not numeros:
        return {}
    lignes = await session.execute(
        select(
            InvoiceProvision.facture_numero,
            func.coalesce(func.sum(InvoiceProvision.prestation_montant_depense), 0),
            func.coalesce(func.sum(InvoiceProvision.prestation_montant_rq), 0),
            func.coalesce(func.sum(InvoiceProvision.prestation_montant_assure), 0),
        )
        .where(InvoiceProvision.facture_numero.in_(numeros))
        .group_by(InvoiceProvision.facture_numero)
    )
    return {
        numero: {
            "montant_depense": depense,
            "montant_rembourse": rembourse,
            "montant_assure": assure,
        }
        for numero, depense, rembourse, assure in lignes
    }


async def _charger_statuts_courants(session, numeros: list[str]) -> dict[str, str]:
    """Retient, pour chaque facture, le dernier statut posé."""

    if not numeros:
        return {}
    lignes = await session.execute(
        select(InvoiceStatus.facture_numero, InvoiceStatus.statut_code)
        .where(InvoiceStatus.facture_numero.in_(numeros))
        .order_by(InvoiceStatus.facture_numero, InvoiceStatus.statut_date_debut)
    )
    # Le tri croissant fait que la dernière écriture dans le dictionnaire est
    # bien le statut le plus récent.
    return {numero: statut for numero, statut in lignes}


async def _charger_assure(session, facture: Invoice) -> InsuredSummarySchema:
    """Assemble l'identité de l'assuré telle qu'elle vaut à la date des soins."""

    assure = await session.get(InsuredPerson, facture.personne_uuid)
    soins = facture.facture_date_soins

    regime = (await session.execute(
        select(Regime).where(Regime.regime_code == assure.regime_code)
        .order_by(Regime.regime_date_debut.desc()).limit(1)
    )).scalar_one_or_none()

    profession = (await session.execute(
        select(InsuredProfession.profession_code)
        .where(InsuredProfession.personne_uuid == facture.personne_uuid)
        .order_by(InsuredProfession.profession_date_debut.desc()).limit(1)
    )).scalar_one_or_none()

    droits = (await session.execute(
        select(InsuredRight.droits_statut).where(
            InsuredRight.personne_uuid == facture.personne_uuid,
            InsuredRight.droits_annee == soins.year,
            InsuredRight.droits_mois == soins.month,
        )
    )).scalar_one_or_none()

    naissance = (await session.execute(
        select(InsuredBirthInfo)
        .where(InsuredBirthInfo.personne_uuid == facture.personne_uuid)
        .order_by(InsuredBirthInfo.naissance_date_debut.desc()).limit(1)
    )).scalar_one_or_none()

    return InsuredSummarySchema(
        personne_uuid=assure.personne_uuid,
        numero_secu=assure.numero_secu,
        civilite_code=assure.civilite_code,
        nom=assure.assure_nom,
        prenoms=assure.assure_prenoms,
        date_naissance=assure.assure_date_naissance,
        regime_code=assure.regime_code,
        regime_libelle=regime.regime_denomination if regime else None,
        regime_taux=regime.regime_taux if regime else None,
        profession_code=profession,
        droits_ouverts=None if droits is None else droits == 1,
        lieu_naissance=naissance.naissance_lieu if naissance else None,
        pays_naissance_code=naissance.pays_code if naissance else None,
    )


async def _charger_entente(session, entente_id: int | None) -> PriorAuthorizationSchema | None:
    """Charge l'entente préalable de la facture et ses actes."""

    if entente_id is None:
        return None
    entente = (await session.execute(
        select(PriorAuthorization)
        .where(PriorAuthorization.entente_prealable_id == entente_id)
        .options(selectinload(PriorAuthorization.medical_acts))
    )).scalar_one_or_none()
    if entente is None:
        return None
    return PriorAuthorizationSchema(
        entente_prealable_id=entente.entente_prealable_id,
        entente_prealable_numero=entente.entente_prealable_numero,
        type_demande_code=entente.type_demande_code,
        type_hospitalisation_code=entente.type_hospitalisation_code,
        date_debut=entente.entente_prealable_date_debut,
        date_fin=entente.entente_prealable_date_fin,
        actes=[
            PriorAuthorizationActSchema(
                acte_medical_code=acte.acte_medical_code,
                professionnel_sante_code=acte.professionnel_sante_code,
                statut=acte.acte_medical_statut,
                taux_remboursement=acte.acte_medical_taux_remboursement,
                montant_cmu=acte.acte_medical_montant_cmu,
                montant_assure=acte.acte_medical_montant_assure,
                motif_rejet=acte.acte_medical_motif_rejet,
            )
            for acte in entente.medical_acts
        ],
    )


@router.get("/{facture_numero}", response_model=InvoiceDetailResponse)
async def get_invoice(facture_numero: str) -> InvoiceDetailResponse:
    """Charge la facture entière : assuré, centre, lignes, entente et totaux."""

    async with async_session_factory() as session:
        statement = select(Invoice).where(Invoice.facture_numero == facture_numero).options(
            selectinload(Invoice.pathologies), selectinload(Invoice.prescriptions),
            selectinload(Invoice.provisions), selectinload(Invoice.statuses),
        )
        invoice = (await session.execute(statement)).scalar_one_or_none()
        if invoice is None:
            raise HTTPException(status_code=404, detail="Facture introuvable.")

        centre = await session.get(HealthCenter, invoice.centre_sante_code)
        assure = await _charger_assure(session, invoice)
        entente = await _charger_entente(session, invoice.entente_prealable_id)

    statuts = sorted(invoice.statuses, key=lambda ligne: ligne.statut_date_debut)
    montant_cmu = sum(
        (acte.montant_cmu or ZERO for acte in entente.actes), ZERO
    ) if entente else ZERO

    return InvoiceDetailResponse(
        facture_numero=invoice.facture_numero, personne_uuid=invoice.personne_uuid,
        centre_sante_code=invoice.centre_sante_code,
        type_facture_code=invoice.type_facture_code,
        facture_date_soins=invoice.facture_date_soins,
        dossier_numero=invoice.dossier_numero,
        produit_code=invoice.produit_code,
        regime_code=invoice.regime_code,
        regime_taux=invoice.regime_taux,
        organisme_code=invoice.organisme_code,
        entente_prealable_id=invoice.entente_prealable_id,
        passage_id=await find_passage_id(facture_numero),
        statut_courant=statuts[-1].statut_code if statuts else None,
        assure=assure,
        centre=HealthCenterSummarySchema(
            centre_sante_code=invoice.centre_sante_code,
            denomination=centre.centre_sante_denomination if centre else None,
            type_code=invoice.centre_sante_type_code,
            type_libelle=invoice.centre_sante_type_libelle,
        ),
        totaux=InvoiceTotalsSchema(
            montant_depense=sum((row.prestation_montant_depense or ZERO for row in invoice.provisions), ZERO),
            montant_rembourse=sum((row.prestation_montant_rq or ZERO for row in invoice.provisions), ZERO),
            montant_assure=sum((row.prestation_montant_assure or ZERO for row in invoice.provisions), ZERO),
            montant_cmu_ententes=montant_cmu,
        ),
        entente_prealable=entente,
        pathologies=[
            InvoicePathologySchema(code=row.pathologie_code, date_debut=row.pathologie_date_debut,
                                   observations=row.pathologie_observations)
            for row in invoice.pathologies
        ],
        prescriptions=[
            InvoicePrescriptionSchema(code=row.prescription_code, date_debut=row.date_debut,
                                      quantite=row.prescription_quantite,
                                      posologie=row.prescription_posologie, duree=row.prescription_duree)
            for row in invoice.prescriptions
        ],
        prestations=[
            InvoiceProvisionSchema(
                code=row.prestation_code,
                professionnel_sante_code=row.professionnel_sante_code,
                statut_remboursement=row.statut_remboursement,
                taux_remboursement=row.prestation_taux_remboursement,
                quantite_prescrite=row.prestation_quantite_prescrite,
                quantite_servie=row.prestation_quantite_servie,
                prix_unitaire=row.prestation_prix_unitaire,
                montant_depense=row.prestation_montant_depense,
                montant_rembourse=row.prestation_montant_rq,
                montant_assure=row.prestation_montant_assure,
            )
            for row in invoice.provisions
        ],
        statuts=[
            InvoiceStatusSchema(code=row.statut_code, date_debut=row.statut_date_debut,
                                observations=row.statut_observations)
            for row in statuts
        ],
    )


@router.get("/{facture_numero}/parcours", response_model=ParcoursResponse)
async def get_invoice_parcours(facture_numero: str) -> ParcoursResponse:
    """Retrace les étapes franchies par une facture, dans l'ordre."""

    passage_id = await find_passage_id(facture_numero)
    if passage_id is None:
        raise HTTPException(
            status_code=404,
            detail="Aucun parcours journalisé pour cette facture.",
        )
    parcours = await build_parcours(passage_id)
    if parcours is None:
        raise HTTPException(status_code=404, detail="Parcours introuvable.")
    return parcours
