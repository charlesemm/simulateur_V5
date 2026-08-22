"""Construit les rapports PDF : technique quotidien, et fiche d'exécution."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from sqlalchemy import func, select

from anomalies.models import AnomalyInjection
from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from metrics.registry import registry
from qualite import analyser
from reports.paths import OUTPUT_DIR
from simulation.models import SimulationRun


def build_daily_pdf_report(jour: date) -> Path:
    """Génère un PDF récapitulant les métriques techniques du registre."""

    donnees = registry.snapshot()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Rapport technique quotidien - Simulateur CMU", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Date du rapport : {jour.isoformat()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    sections = [
        ("Disponibilité de l'API", [
            ("Serveur démarré depuis", donnees["demarre_depuis"]),
            ("Uptime (secondes)", donnees["uptime_secondes"]),
            ("Requêtes API traitées", donnees["requetes_api_total"]),
            ("Temps de réponse moyen (ms)", donnees["temps_moyen_reponse_api_ms"]),
        ]),
        ("Moteur de simulation", [
            ("Passages réussis", donnees["passages_reussis"]),
            ("Passages échoués", donnees["passages_echoues"]),
            ("Taux d'échec (%)", donnees["taux_echec_pourcent"]),
            ("Pic de passages simultanés atteint", donnees["pic_passages_simultanes"]),
        ]),
        ("Pipeline KPI (étape 4)", [
            ("Recalculs déclenchés", donnees["recalculs_kpi"]),
            ("Temps moyen par recalcul (ms)", donnees["temps_moyen_recalcul_kpi_ms"]),
        ]),
        ("Connexions temps réel (Socket.IO)", [
            ("Connexions totales", donnees["connexions_socketio_total"]),
            ("Déconnexions totales", donnees["deconnexions_socketio_total"]),
            ("Clients actuellement connectés", donnees["clients_socketio_actifs"]),
        ]),
    ]

    for titre, paires in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, titre, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 11)
        for libelle, valeur in paires:
            pdf.cell(0, 7, f"    {libelle} : {valeur}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        "Ce rapport ne contient volontairement aucune métrique métier CMU "
        "(montants, pathologies, ententes) -- uniquement des indicateurs sur "
        "le fonctionnement technique du simulateur.",
    )

    chemin = OUTPUT_DIR / f"rapport_technique_{jour.isoformat()}.pdf"
    pdf.output(str(chemin))
    return chemin


def _sans_accents(valeur: str) -> str:
    """FPDF écrit en latin-1 : les caractères hors jeu casseraient la sortie."""

    return str(valeur).encode("latin-1", "replace").decode("latin-1")


async def build_execution_pdf_report(simulation_id: UUID) -> Path:
    """Génère la fiche d'une exécution : paramètres, volumétrie et qualité.

    Contrairement au rapport quotidien, qui lit le registre en mémoire, cette
    fiche se construit entièrement depuis la base : elle reste juste après un
    redémarrage, et vaut pour n'importe quelle exécution passée.
    """

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)
        if execution is None:
            raise LookupError(f"Exécution inconnue : {simulation_id}.")

        async def compter(modele) -> int:
            return (await session.execute(
                select(func.count()).select_from(modele)
                .where(modele.simulation_id == simulation_id)
            )).scalar_one()

        volumetrie = [
            ("Factures", await compter(Invoice)),
            ("Prestations", await compter(InvoiceProvision)),
            ("Ententes prealables", await compter(PriorAuthorization)),
            ("Evenements", await compter(EventJournal)),
            ("Anomalies injectees", await compter(AnomalyInjection)),
        ]

    qualite = await analyser(simulation_id, inclure_referentiel=False)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Fiche d'execution - ECHO, CNAM-CI", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, _sans_accents(execution.simulation_libelle), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Identifiant : {execution.simulation_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Type : {execution.simulation_type or 'non precise'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Statut : {execution.simulation_statut}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Debut : {execution.simulation_date_debut.isoformat()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Fin : {execution.simulation_date_fin.isoformat()
                            if execution.simulation_date_fin else 'en cours'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    sections: list[tuple[str, list[tuple[str, object]]]] = [
        ("Passages", [
            ("Reussis", execution.passages_reussis),
            ("Echoues", execution.passages_echoues),
        ]),
        ("Volumetrie produite", volumetrie),
        ("Constats de qualite par dimension", list(qualite["par_dimension"].items())),
    ]

    for titre, paires in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, _sans_accents(titre), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 11)
        for libelle, valeur in paires:
            pdf.cell(0, 7, _sans_accents(f"    {libelle} : {valeur}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    if qualite["confrontation"]:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Anomalies : injectees contre detectees", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 11)
        for ligne in qualite["confrontation"]:
            taux = ligne["taux_detection_pourcent"]
            pdf.cell(0, 7, _sans_accents(
                f"    {ligne['anomalie_code']} : {ligne['injectees']} injectees, "
                f"{ligne['detectees']} detectees"
                + (f" ({taux} %)" if taux is not None else "")
            ), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        "Le taux de detection compare ce que les regles de qualite relevent a "
        "ce que le journal d'injection dit avoir pose. C'est la seule mesure "
        "qu'aucun outil branche sur des donnees reelles ne peut produire.",
    )

    chemin = OUTPUT_DIR / f"execution_{simulation_id}.pdf"
    pdf.output(str(chemin))
    return chemin