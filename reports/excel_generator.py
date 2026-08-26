"""Construit l'export Excel multi-feuilles des données générées ce jour-là."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy import select

from app.database import async_session_factory
from app.models import InsuredPerson, Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from reports.paths import OUTPUT_DIR


async def _numeros_secu(session, lignes) -> dict[UUID, str]:
    """Associe à chaque assuré cité son numéro de sécurité sociale.

    L'export identifiait les personnes par leur UUID technique — un
    identifiant interne, illisible et sans valeur pour qui reçoit le fichier.
    Le numéro de sécurité sociale est l'identifiant métier : c'est lui qui
    permet de rapprocher une ligne d'un dossier réel.

    `lignes` est n'importe quel mélange d'objets portant un `personne_uuid` —
    factures, ententes — résolu en **une seule** requête : les mêmes personnes
    reviennent d'une table à l'autre, et les interroger table par table
    multiplierait les allers-retours sans rien apporter.
    """

    uuids = {
        ligne.personne_uuid for ligne in lignes
        if getattr(ligne, "personne_uuid", None)
    }
    if not uuids:
        return {}

    lignes = await session.execute(
        select(InsuredPerson.personne_uuid, InsuredPerson.numero_secu)
        .where(InsuredPerson.personne_uuid.in_(uuids))
    )
    return {identifiant: numero for identifiant, numero in lignes}


def _bornes_journee(jour: date) -> tuple[datetime, datetime]:
    """Renvoie les bornes [00:00, 23:59:59] du jour, en UTC."""

    debut = datetime.combine(jour, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(jour, time.max, tzinfo=timezone.utc)
    return debut, fin


async def build_daily_excel_export(jour: date) -> Path:
    """Exporte une journée entière. Cas particulier de l'export par période."""

    debut, fin = _bornes_journee(jour)
    return await build_excel_export(
        debut, fin, libelle=f"Journée du {jour.isoformat()}",
        nom_fichier=f"export_donnees_{jour.isoformat()}",
    )


def _restreindre(requete, modele, debut: datetime | None, fin: datetime | None,
                 simulation_id: UUID | None):
    """Applique la fenêtre de temps et l'exécution, quand elles sont fournies.

    Filtrer sur l'exécution suffit à isoler ce qu'elle a produit : les bornes
    de temps ne servent alors qu'à découper à l'intérieur.
    """

    if debut is not None and fin is not None:
        requete = requete.where(modele.date_creation.between(debut, fin))
    if simulation_id is not None:
        requete = requete.where(modele.simulation_id == simulation_id)
    return requete


async def build_excel_export(debut: datetime | None = None, fin: datetime | None = None,
                             simulation_id: UUID | None = None,
                             libelle: str = "Export", nom_fichier: str = "export") -> Path:
    """Exporte les factures, prestations, ententes et événements d'un périmètre.

    Le périmètre est une période, une exécution, ou les deux : c'est ce qui
    permet de sortir aussi bien le jeu de données d'un run que celui d'un mois.
    """

    classeur = Workbook()
    compteurs: dict[str, int] = {}

    async with async_session_factory() as session:
        factures = list((await session.execute(
            _restreindre(select(Invoice), Invoice, debut, fin, simulation_id)
        )).scalars())
        compteurs["Factures"] = len(factures)
        secu = await _numeros_secu(session, factures)

        feuille = classeur.create_sheet("Factures")
        feuille.append([
            "Numéro facture", "Numéro de sécurité sociale", "Centre",
            "Type facture", "Date des soins", "Dossier", "Créée le",
        ])
        for f in factures:
            feuille.append([
                f.facture_numero, secu.get(f.personne_uuid, "—"), f.centre_sante_code,
                f.type_facture_code, f.facture_date_soins.isoformat(),
                f.dossier_numero, f.date_creation.isoformat(),
            ])

        prestations = list((await session.execute(
            _restreindre(select(InvoiceProvision), InvoiceProvision, debut, fin, simulation_id)
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
            _restreindre(select(PriorAuthorization), PriorAuthorization, debut, fin, simulation_id)
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
            _restreindre(select(EventJournal), EventJournal, debut, fin, simulation_id)
            .order_by(EventJournal.simulated_at).limit(2000)
        )).scalars())
        compteurs["Événements techniques (max. 2000)"] = len(evenements)
        feuille = classeur.create_sheet("Journal technique")
        feuille.append(["Type d'événement", "Passage", "Horodatage simulé"])
        for ev in evenements:
            feuille.append([ev.type_evenement, ev.passage_id, ev.simulated_at.isoformat()])

    resume = classeur.active
    resume.title = "Résumé"
    resume.append(["Export de données -- ÉCHO, CNAM-CI"])
    resume.append(["Périmètre", libelle])
    if simulation_id is not None:
        resume.append(["Exécution", str(simulation_id)])
    if debut is not None and fin is not None:
        resume.append(["Du", debut.isoformat()])
        resume.append(["Au", fin.isoformat()])
    resume.append([])
    resume.append(["Feuille", "Lignes exportées"])
    for nom, total in compteurs.items():
        resume.append([nom, total])

    chemin = OUTPUT_DIR / f"{nom_fichier}.xlsx"
    classeur.save(chemin)
    return chemin