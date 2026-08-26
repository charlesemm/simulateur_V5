"""Consultation et génération manuelle des rapports quotidiens."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.database import async_session_factory
from auth.dependencies import require_role
from simulation.models import SimulationRun
from reports.csv_generator import build_csv_export
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


@router.get("/executions")
async def list_rapports_executions(jour: date | None = None) -> list[dict]:
    """Les exécutions d'une journée, avec les rapports déjà produits pour chacune.

    Les fichiers portent l'identifiant technique de l'exécution
    (`execution_<uuid>.pdf`) : illisible, et impossible à rapprocher d'une
    simulation sans passer par la base. On fait donc ce rapprochement ici,
    pour que l'écran puisse les présenter sous le **nom** que l'opérateur a
    donné au départ.

    Sans jour précisé, on rend les exécutions du jour même.
    """

    vise = jour or date.today()
    debut = datetime.combine(vise, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(vise, time.max, tzinfo=timezone.utc)

    async with async_session_factory() as session:
        executions = list((await session.execute(
            select(SimulationRun)
            .where(SimulationRun.simulation_date_debut.between(debut, fin))
            .order_by(SimulationRun.simulation_date_debut.desc())
        )).scalars())

    fiches = []
    for execution in executions:
        base = f"execution_{execution.simulation_id}"
        # Un fichier n'est proposé que s'il existe vraiment sur le disque :
        # une purge des rapports laisse les exécutions en base, et proposer
        # un téléchargement mort serait pire que ne rien proposer.
        fichiers = {
            "pdf": f"{base}.pdf" if (OUTPUT_DIR / f"{base}.pdf").is_file() else None,
            "excel": f"{base}.xlsx" if (OUTPUT_DIR / f"{base}.xlsx").is_file() else None,
            "csv": f"{base}.csv.zip" if (OUTPUT_DIR / f"{base}.csv.zip").is_file() else None,
        }
        fiches.append({
            "simulation_id": str(execution.simulation_id),
            "simulation_libelle": execution.simulation_libelle,
            "simulation_type": execution.simulation_type,
            "simulation_statut": execution.simulation_statut,
            "simulation_date_debut": execution.simulation_date_debut.isoformat(),
            "simulation_date_fin": (
                execution.simulation_date_fin.isoformat()
                if execution.simulation_date_fin else None
            ),
            "passages_reussis": execution.passages_reussis,
            "fichiers": fichiers,
        })
    return fiches


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
    nom = f"export_periode_{date_min.isoformat()}_{date_max.isoformat()}"
    libelle_p = f"Du {date_min.isoformat()} au {date_max.isoformat()}"
    chemin_excel = await build_excel_export(debut, fin, libelle=libelle_p, nom_fichier=nom)
    chemin_csv = await build_csv_export(debut, fin, nom_fichier=nom)
    return {"excel": chemin_excel.name, "csv": chemin_csv.name}


@router.post("/execution/{simulation_id}")
async def generate_execution(simulation_id: UUID) -> dict[str, str]:
    """Produit le jeu de données et la fiche PDF d'une exécution."""

    try:
        pdf = await build_execution_pdf_report(simulation_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente

    nom = f"execution_{simulation_id}"
    excel = await build_excel_export(
        simulation_id=simulation_id,
        libelle=f"Exécution {simulation_id}",
        nom_fichier=nom,
    )
    csv_zip = await build_csv_export(simulation_id=simulation_id, nom_fichier=nom)
    return {"pdf": pdf.name, "excel": excel.name, "csv": csv_zip.name}


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