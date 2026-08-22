"""Expose les moteurs MDM, entrepôt et gouvernance."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from auth.dependencies import require_role
from entrepot import approfondir_historique
from gouvernance import (
    CATALOGUE, inventaire, panorama, panorama_markdown, rapport, volumetrie,
)
from mdm import VARIATIONS, evaluer, generer_variantes, lire_paires
from seed.provenance import HYPOTHESES, LIBELLES_NATURE, REFERENTIELS, resume

router = APIRouter(tags=["Moteurs"])


# ── T2 : rapprochement d'identités ───────────────────────────────────────

class GenerationMdmRequest(BaseModel):
    """Paramètre la fabrique d'identités jumelles."""

    simulation_id: UUID | None = None
    nombre: int = Field(default=20, ge=1, le=1000)
    part_leurres: float = Field(default=0.25, ge=0.0, le=1.0)
    graine: int = 42


class EvaluationMdmRequest(BaseModel):
    """Soumet un rapprochement proposé, pour notation."""

    simulation_id: UUID | None = None
    # Chaque paire est un couple d'identifiants d'assurés, dans n'importe
    # quel ordre : le rapprochement n'est pas orienté.
    paires: list[tuple[str, str]]


@router.post("/mdm/generer", dependencies=[Depends(require_role("operateur"))])
async def generer_mdm(requete: GenerationMdmRequest) -> dict:
    """Fabrique des identités jumelles et consigne la vérité terrain."""

    try:
        return await generer_variantes(
            requete.simulation_id, requete.nombre, requete.part_leurres, requete.graine
        )
    except RuntimeError as vide:
        raise HTTPException(status_code=409, detail=str(vide)) from vide


@router.get("/mdm/verite-terrain", dependencies=[Depends(require_role("observateur"))])
async def verite_terrain(simulation_id: UUID | None = None) -> list[dict]:
    """Retourne les paires fabriquées, avec la réponse attendue."""

    return [
        {
            "paire_id": str(paire.paire_id),
            "simulation_id": str(paire.simulation_id) if paire.simulation_id else None,
            "personne_uuid_source": str(paire.personne_uuid_source),
            "personne_uuid_variante": str(paire.personne_uuid_variante),
            "type_variation": paire.type_variation,
            "meme_personne": paire.meme_personne,
            "commentaire": paire.commentaire,
        }
        for paire in await lire_paires(simulation_id)
    ]


@router.get("/mdm/variations", dependencies=[Depends(require_role("observateur"))])
async def list_variations() -> list[str]:
    """Retourne les types de variation que le générateur sait produire."""

    return list(VARIATIONS)


@router.post("/mdm/evaluer", dependencies=[Depends(require_role("observateur"))])
async def evaluer_mdm(requete: EvaluationMdmRequest) -> dict:
    """Note un rapprochement proposé : précision, rappel et F-mesure."""

    return await evaluer(requete.paires, requete.simulation_id)


# ── T3 : entrepôt de données ─────────────────────────────────────────────

class HistoriqueRequest(BaseModel):
    """Paramètre la profondeur d'historique à produire."""

    simulation_id: UUID | None = None
    mois: int = Field(default=12, ge=1, le=120)
    assures: int = Field(default=50, ge=1, le=5000)
    graine: int = 42


@router.post("/entrepot/historique", dependencies=[Depends(require_role("operateur"))])
async def generer_historique(requete: HistoriqueRequest) -> dict:
    """Ajoute des mois de droits et des versions de profession."""

    try:
        return await approfondir_historique(
            requete.mois, requete.assures, requete.simulation_id, requete.graine
        )
    except RuntimeError as vide:
        raise HTTPException(status_code=409, detail=str(vide)) from vide


# ── T4 : gouvernance ─────────────────────────────────────────────────────

@router.get("/gouvernance/catalogue", dependencies=[Depends(require_role("observateur"))])
async def catalogue_gouvernance() -> list[dict]:
    """Retourne l'inventaire déclaré : domaine, propriétaire, criticité."""

    return [
        {
            "table": fiche.table,
            "domaine": fiche.domaine,
            "description": fiche.description,
            "proprietaire": fiche.proprietaire,
            "criticite": fiche.criticite,
            "donnees_personnelles": fiche.donnees_personnelles,
        }
        for fiche in CATALOGUE
    ]


@router.get("/gouvernance/inventaire", dependencies=[Depends(require_role("observateur"))])
async def inventaire_gouvernance() -> dict:
    """Confronte le catalogue aux tables réellement présentes en base."""

    return await inventaire()


@router.get("/gouvernance/volumetrie", dependencies=[Depends(require_role("observateur"))])
async def volumetrie_gouvernance() -> list[dict]:
    """Compte les lignes de chaque table du catalogue."""

    return await volumetrie()


@router.get("/gouvernance/panorama", dependencies=[Depends(require_role("observateur"))])
async def panorama_gouvernance() -> list[dict]:
    """Décrit toutes les tables en base : colonnes, clés, volumes, propriétaire."""

    return await panorama()


@router.get("/gouvernance/panorama.md", dependencies=[Depends(require_role("observateur"))])
async def panorama_markdown_gouvernance() -> PlainTextResponse:
    """Rend le même panorama en Markdown, prêt à déposer dans la documentation."""

    return PlainTextResponse(await panorama_markdown(), media_type="text/markdown")


@router.get("/gouvernance/provenance", dependencies=[Depends(require_role("observateur"))])
async def provenance_gouvernance() -> dict:
    """Dit quels référentiels sont inventés et quelles hypothèses tiennent lieu de faits.

    Une fois en base, rien ne distingue une nomenclature reconstituée d'une
    nomenclature officielle : ce point d'accès rétablit la différence.
    """

    return {
        "resume": resume(),
        "libelles_nature": LIBELLES_NATURE,
        "referentiels": [
            {
                "cle": referentiel.cle,
                "libelle": referentiel.libelle,
                "nature": referentiel.nature,
                "entrees": referentiel.entrees,
                "table_cible": referentiel.table_cible,
                "note": referentiel.note,
            }
            for referentiel in REFERENTIELS
        ],
        "hypotheses": [
            {
                "cle": hypothese.cle,
                "libelle": hypothese.libelle,
                "valeur": hypothese.valeur,
                "fondement": hypothese.fondement,
                "consequence": hypothese.consequence,
            }
            for hypothese in HYPOTHESES
        ],
    }


@router.get("/gouvernance/rapport", dependencies=[Depends(require_role("observateur"))])
async def rapport_gouvernance(simulation_id: UUID | None = None) -> dict:
    """Assemble inventaire, lignage et violations de règles."""

    try:
        return await rapport(simulation_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente
