"""Consultation du parcours d'un passage, étape par étape."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from echo.web.api.schema import ParcoursResponse
from echo.web.api.services.parcours import build_parcours
from echo.web.auth.dependencies import require_role

# Le parcours expose des données de santé au même titre que la facture.
router = APIRouter(
    prefix="/parcours",
    tags=["Parcours"],
    dependencies=[Depends(require_role("observateur"))],
)


@router.get("/{passage_id}", response_model=ParcoursResponse)
async def get_parcours(passage_id: str) -> ParcoursResponse:
    """Retrace les étapes d'un passage à partir de son identifiant."""

    parcours = await build_parcours(passage_id)
    if parcours is None:
        raise HTTPException(
            status_code=404,
            detail="Aucun événement journalisé pour ce passage.",
        )
    return parcours
