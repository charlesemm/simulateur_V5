"""Construit l'export Excel multi-feuilles des données générées ce jour-là."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from reports.paths import OUTPUT_DIR


def _bornes_journee(jour: date) -> tuple[datetime, datetime]:
    """Renvoie les bornes [00:00, 23:59:59] du jour, en UTC."""

    debut = datetime.combine(jour, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(jour, time.max, tzinfo=timezone.utc)
    return debut, fin


async def build_daily_excel_export(jour: date) -> Path:
    """Exporte les factures, prestations, ententes et événements du jour."""

    debut, fin = _bornes_journee(jour)
    classeur = Workbook()
    compteurs: dict[str, int] = {}

    async with async_session_factory() as session:
        factures = list((await session.execute(
            select(Invoice).where(Invoice.date_creation.between(debut, fin))
        )).scalars())
        compteurs["Factures"] = len(factures)
        feuille = classeur.create_sheet("Factures")
        feuille.append([
            "Numéro facture", "Assuré (UUID)", "Centre", "Type facture",
            "Date des soins", "Dossier", "Créée le",
        ])
        for f in factures:
            feuille.append([
                f.facture_numero, str(f.personne_uuid), f.centre_sante_code,
                f.type_facture_code, f.facture_date_soins.isoformat(),
                f.dossier_numero, f.date_creation.isoformat(),
            ])

        prestations = list((await session.execute(
            select(InvoiceProvision).where(InvoiceProvision.date_creation.between(debut, fin))
        )).scalars())
        compteurs["Prestations"] = len(prestations)
        feuille = classeur.create_sheet("Prestations")
        feuille.append([
            "Facture", "Prestation", "Professionnel", "Statut remboursement",
            "Montant dépensé", "Montant remboursé", "Montant assuré",
        ])
        for p in prestations:
            feuille.append([
                p.facture_numero, p.prestation_code, p.professionnel_sante_code,
                p.statut_remboursement, float(p.prestation_montant_depense or 0),
                float(p.prestation_montant_rq or 0), float(p.prestation_montant_assure or 0),
            ])

        ententes = list((await session.execute(
            select(PriorAuthorization).where(PriorAuthorization.date_creation.between(debut, fin))
        )).scalars())
        compteurs["Ententes préalables"] = len(ententes)
        feuille = classeur.create_sheet("Ententes préalables")
        feuille.append([
            "Numéro entente", "Centre", "Assuré (UUID)", "Dossier",
            "Type demande", "Date début", "Facture liée",
        ])
        for e in ententes:
            feuille.append([
                e.entente_prealable_numero, e.centre_sante_code, str(e.personne_uuid),
                e.dossier_numero, e.type_demande_code,
                e.entente_prealable_date_debut.isoformat(), e.facture_numero or "",
            ])

        # Limité à 2000 lignes : le journal technique peut grossir vite,
        # inutile de tout charger dans un fichier destiné à être lu à l'oeil.
        evenements = list((await session.execute(
            select(EventJournal).where(EventJournal.date_creation.between(debut, fin))
            .order_by(EventJournal.simulated_at).limit(2000)
        )).scalars())
        compteurs["Événements techniques (max. 2000)"] = len(evenements)
        feuille = classeur.create_sheet("Journal technique")
        feuille.append(["Type d'événement", "Passage", "Horodatage simulé"])
        for ev in evenements:
            feuille.append([ev.type_evenement, ev.passage_id, ev.simulated_at.isoformat()])

    resume = classeur.active
    resume.title = "Résumé"
    resume.append(["Export de données -- Simulateur CMU"])
    resume.append(["Date", jour.isoformat()])
    resume.append([])
    resume.append(["Feuille", "Lignes exportées"])
    for nom, total in compteurs.items():
        resume.append([nom, total])

    chemin = OUTPUT_DIR / f"export_donnees_{jour.isoformat()}.xlsx"
    classeur.save(chemin)
    return chemin