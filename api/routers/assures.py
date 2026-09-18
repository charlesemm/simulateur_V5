"""Consultation du référentiel assuré : recherche et fiche."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from app.database import async_session_factory
from app.models import (
    InsuredBirthInfo, InsuredPerson, InsuredProfession, InsuredRight, Invoice,
)
from auth.dependencies import require_role

# Le référentiel porte des données personnelles : aucun accès anonyme.
router = APIRouter(
    prefix="/assures",
    tags=["Assurés"],
    dependencies=[Depends(require_role("observateur"))],
)


# Caractère d'échappement des motifs LIKE : une seule barre oblique inverse.
ECHAPPEMENT = "\\"


def _motif_recherche(saisie: str) -> str:
    """Prépare un motif ILIKE où « % » et « _ » restent des caractères.

    Sans échappement, un « % » saisi n'était pas cherché mais interprété :
    la recherche rendait tout le référentiel, au prix de quatre parcours
    complets de la table.
    """

    echappee = (
        saisie.strip()
        .replace(ECHAPPEMENT, ECHAPPEMENT * 2)
        .replace("%", f"{ECHAPPEMENT}%")
        .replace("_", f"{ECHAPPEMENT}_")
    )
    return f"%{echappee}%"


@router.get("")
async def list_assures(recherche: str | None = None,
                       limite: int = Query(default=50, ge=1, le=200),
                       decalage: int = Query(default=0, ge=0)) -> dict:
    """Recherche par nom, prénoms ou numéro, et retourne une page d'assurés."""

    async with async_session_factory() as session:
        base = select(InsuredPerson)
        if recherche:
            motif = _motif_recherche(recherche)
            base = base.where(or_(
                InsuredPerson.assure_nom.ilike(motif, escape=ECHAPPEMENT),
                InsuredPerson.assure_prenoms.ilike(motif, escape=ECHAPPEMENT),
                InsuredPerson.numero_secu.ilike(motif, escape=ECHAPPEMENT),
                InsuredPerson.assure_numero_identifiant.ilike(motif, escape=ECHAPPEMENT),
            ))

        total = (await session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()

        assures = list((await session.execute(
            base.order_by(InsuredPerson.assure_nom, InsuredPerson.assure_prenoms)
            .offset(decalage).limit(limite)
        )).scalars())

        # Droits du mois en cours, pour la seule page affichée : c'est ce que
        # l'accueil regarde avant d'ouvrir une facture.
        maintenant = datetime.now(timezone.utc)
        identifiants = [assure.personne_uuid for assure in assures]
        droits = dict((await session.execute(
            select(InsuredRight.personne_uuid, InsuredRight.droits_statut).where(
                InsuredRight.personne_uuid.in_(identifiants),
                InsuredRight.droits_annee == maintenant.year,
                InsuredRight.droits_mois == maintenant.month,
            )
        )).all()) if identifiants else {}

    return {
        "total": total,
        "limite": limite,
        "decalage": decalage,
        "assures": [
            {
                "personne_uuid": str(assure.personne_uuid),
                "numero_secu": assure.numero_secu,
                "numero_identifiant": assure.assure_numero_identifiant,
                "nom": assure.assure_nom,
                "prenoms": assure.assure_prenoms,
                "date_naissance": (
                    assure.assure_date_naissance.isoformat()
                    if assure.assure_date_naissance else None
                ),
                "regime_code": assure.regime_code,
                "droits_ouverts": droits.get(assure.personne_uuid) == 1,
            }
            for assure in assures
        ],
    }


@router.get("/{personne_uuid}")
async def get_assure(personne_uuid: UUID) -> dict:
    """Retourne la fiche d'un assuré : identité, droits, professions, factures."""

    async with async_session_factory() as session:
        assure = await session.get(InsuredPerson, personne_uuid)
        if assure is None:
            raise HTTPException(status_code=404, detail="Assuré introuvable.")

        droits = list((await session.execute(
            select(InsuredRight)
            .where(InsuredRight.personne_uuid == personne_uuid)
            .order_by(InsuredRight.droits_annee.desc(), InsuredRight.droits_mois.desc())
            .limit(24)
        )).scalars())

        professions = list((await session.execute(
            select(InsuredProfession)
            .where(InsuredProfession.personne_uuid == personne_uuid)
            .order_by(InsuredProfession.profession_date_debut.desc())
        )).scalars())

        naissance = (await session.execute(
            select(InsuredBirthInfo)
            .where(InsuredBirthInfo.personne_uuid == personne_uuid)
            .order_by(InsuredBirthInfo.naissance_date_debut.desc()).limit(1)
        )).scalar_one_or_none()

        factures = (await session.execute(
            select(func.count()).select_from(Invoice)
            .where(Invoice.personne_uuid == personne_uuid)
        )).scalar_one()

    return {
        "personne_uuid": str(assure.personne_uuid),
        "numero_secu": assure.numero_secu,
        "numero_identifiant": assure.assure_numero_identifiant,
        "civilite_code": assure.civilite_code,
        "nom": assure.assure_nom,
        "prenoms": assure.assure_prenoms,
        "date_naissance": (
            assure.assure_date_naissance.isoformat()
            if assure.assure_date_naissance else None
        ),
        "regime_code": assure.regime_code,
        "lieu_naissance": naissance.naissance_lieu if naissance else None,
        "pays_naissance_code": naissance.pays_code if naissance else None,
        "factures": factures,
        "droits": [
            {
                "annee": ligne.droits_annee,
                "mois": ligne.droits_mois,
                "ouverts": ligne.droits_statut == 1,
            }
            for ligne in droits
        ],
        "professions": [
            {
                "code": ligne.profession_code,
                "date_debut": ligne.profession_date_debut.isoformat(),
                "date_fin": (
                    ligne.profession_date_fin.isoformat()
                    if ligne.profession_date_fin else None
                ),
            }
            for ligne in professions
        ],
    }
