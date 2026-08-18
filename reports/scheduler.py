"""Planifie la génération quotidienne des rapports et l'expose à la demande."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from reports.excel_generator import build_daily_excel_export
from reports.pdf_generator import build_daily_pdf_report

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def generate_reports_for_day(jour: date) -> dict[str, str]:
    """Génère les deux rapports (PDF + Excel) pour le jour indiqué."""

    pdf_path = build_daily_pdf_report(jour)
    excel_path = await build_daily_excel_export(jour)
    logger.info("Rapports générés pour %s : %s, %s", jour, pdf_path.name, excel_path.name)
    return {"pdf": pdf_path.name, "excel": excel_path.name}


async def _job_minuit() -> None:
    """Génère le rapport de la journée qui vient de s'achever."""

    hier = date.today() - timedelta(days=1)
    await generate_reports_for_day(hier)


def start_scheduler() -> None:
    scheduler.add_job(_job_minuit, CronTrigger(hour=0, minute=0), id="rapports_quotidiens", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)