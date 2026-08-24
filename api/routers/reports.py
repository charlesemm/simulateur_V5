"""Consultation et génération manuelle des rapports quotidiens."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth.dependencies import require_role
from reports.excel_generator import build_excel_export
from reports.paths import OUTPUT_DIR
from reports.pdf_generator import build_execution_pdf_report
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


@router.post("/periode")
async def generate_periode(date_min: date, date_max: date) -> dict[str, str]:
    """Exporte les données produites entre deux dates, bornes comprises."""

    if date_max < date_min:
        raise HTTPException(
            status_code=422, detail="La date de fin précède la date de début."
        )

    debut = datetime.combine(date_min, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(date_max, time.max, tzinfo=timezone.utc)
    chemin = await build_excel_export(
        debut, fin,
        libelle=f"Du {date_min.isoformat()} au {date_max.isoformat()}",
        nom_fichier=f"export_periode_{date_min.isoformat()}_{date_max.isoformat()}",
    )
    return {"excel": chemin.name}


@router.post("/execution/{simulation_id}")
async def generate_execution(simulation_id: UUID) -> dict[str, str]:
    """Produit le jeu de données et la fiche PDF d'une exécution."""

    try:
        pdf = await build_execution_pdf_report(simulation_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente

    excel = await build_excel_export(
        simulation_id=simulation_id,
        libelle=f"Exécution {simulation_id}",
        nom_fichier=f"execution_{simulation_id}",
    )
    return {"pdf": pdf.name, "excel": excel.name}


@router.delete("", dependencies=[Depends(require_role("administrateur"))])
async def purge_reports() -> dict[str, int]:
    """Supprime tous les rapports générés sur le disque.

    Seul un administrateur peut le faire : la suppression est irréversible.
    """

    supprimes = 0
    for fichier in OUTPUT_DIR.iterdir():
        if fichier.is_file():
            fichier.unlink()
            supprimes += 1
    return {"supprimes": supprimes}


@router.get("/{nom_fichier}")
async def download_report(nom_fichier: str) -> FileResponse:
    """Télécharge un rapport précis, en se protégeant d'un chemin détourné."""

    chemin = (OUTPUT_DIR / nom_fichier).resolve()
    if chemin.parent != OUTPUT_DIR.resolve() or not chemin.is_file():
        raise HTTPException(status_code=404, detail="Rapport introuvable.")
    return FileResponse(chemin, filename=nom_fichier)