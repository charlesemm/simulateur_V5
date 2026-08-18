"""Construit le rapport technique quotidien au format PDF."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from metrics.registry import registry
from reports.paths import OUTPUT_DIR


def build_daily_pdf_report(jour: date) -> Path:
    """Génère un PDF récapitulant les métriques techniques du registre."""

    donnees = registry.snapshot()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Rapport technique quotidien - Simulateur CMU", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Date du rapport : {jour.isoformat()}", ln=True)
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
        pdf.cell(0, 9, titre, ln=True)
        pdf.set_font("Helvetica", "", 11)
        for libelle, valeur in paires:
            pdf.cell(0, 7, f"    {libelle} : {valeur}", ln=True)
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