"""Consultation et génération manuelle des rapports quotidiens."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth.dependencies import require_role
from reports.paths import OUTPUT_DIR
from reports.scheduler import generate_reports_for_day

router = APIRouter(
    prefix="/reports",
    tags=["rapports"],
    dependencies=[Depends(require_role("operateur"))],
)


@router.get("")
async def list_reports() -> list[str]:
    """Liste les rapports déjà générés, du plus récent au plus ancien."""

    fichiers = sorted(OUTPUT_DIR.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [f.name for f in fichiers]


@router.post("/generate")
async def generate_report(jour: date | None = None) -> dict[str, str]:
    """Déclenche la génération manuelle pour le jour indiqué (aujourd'hui par défaut)."""

    return await generate_reports_for_day(jour or date.today())


@router.get("/{nom_fichier}")
async def download_report(nom_fichier: str) -> FileResponse:
    """Télécharge un rapport précis, en se protégeant d'un chemin détourné."""

    chemin = (OUTPUT_DIR / nom_fichier).resolve()
    if chemin.parent != OUTPUT_DIR.resolve() or not chemin.is_file():
        raise HTTPException(status_code=404, detail="Rapport introuvable.")
    return FileResponse(chemin, filename=nom_fichier)