"""Expose le rapport de qualité des données d'une exécution."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import require_role
from qualite import REGLES, analyser

router = APIRouter(prefix="/qualite", tags=["Qualité"])


@router.get("/regles", dependencies=[Depends(require_role("observateur"))])
async def list_regles() -> list[dict]:
    """Retourne les règles appliquées, avec l'anomalie que chacune cherche."""

    return [
        {
            "code": regle.code,
            "libelle": regle.libelle,
            "dimension": regle.dimension,
            "anomalie_visee": regle.anomalie_code,
            "referentielle": regle.referentielle,
        }
        for regle in REGLES
    ]


@router.get("/rapport", dependencies=[Depends(require_role("observateur"))])
async def rapport(simulation_id: UUID | None = None,
                  inclure_referentiel: bool = True) -> dict:
    """Analyse une exécution et confronte les constats au journal d'injection.

    Sans `simulation_id`, l'analyse porte sur l'ensemble des données en base.
    """

    try:
        return await analyser(simulation_id, inclure_referentiel)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente
