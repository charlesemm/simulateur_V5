"""Exporte les données en fichiers CSV, un par table.

Contrairement à l'Excel multi-feuilles, le CSV produit un fichier ZIP
contenant un CSV par table : c'est le format que les outils d'import
(pandas, DBeaver, pgAdmin, SSIS) consomment le plus naturellement.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from reports.paths import OUTPUT_DIR


def _restreindre(requete, modele, debut: datetime | None, fin: datetime | None,
                 simulation_id: UUID | None):
    """Applique la fenêtre de temps et l'exécution."""

    if debut is not None and fin is not None:
        requete = requete.where(modele.date_creation.between(debut, fin))
    if simulation_id is not None:
        requete = requete.where(modele.simulation_id == simulation_id)
    return requete


def _csv_bytes(entetes: list[str], lignes: list[list]) -> bytes:
    """Sérialise un jeu de données en CSV UTF-8 avec BOM (pour Excel)."""

    tampon = io.StringIO()
    tampon.write("﻿")  # BOM pour qu'Excel détecte l'UTF-8
    ecrivain = csv.writer(tampon, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    ecrivain.writerow(entetes)
    ecrivain.writerows(lignes)
    return tampon.getvalue().encode("utf-8")


async def build_csv_export(
    debut: datetime | None = None,
    fin: datetime | None = None,
    simulation_id: UUID | None = None,
    nom_fichier: str = "export",
) -> Path:
    """Produit un ZIP contenant un CSV par table.

    Le ZIP est le format le plus pratique pour distribuer plusieurs CSV
    sans perdre l'association entre les fichiers.
    """

    fichiers_csv: dict[str, bytes] = {}

    async with async_session_factory() as session:
        # ── Factures ─────────────────────────────────────────────────
        factures = list((await session.execute(
            _restreindre(select(Invoice), Invoice, debut, fin, simulation_id)
        )).scalars())
        fichiers_csv["factures.csv"] = _csv_bytes(
            ["numero_facture", "assure_uuid", "centre_sante_code", "type_facture",
             "regime_code", "regime_taux", "date_soins", "dossier_numero",
             "centre_type_code", "centre_type_libelle", "date_creation"],
            [[
                f.facture_numero, str(f.personne_uuid), f.centre_sante_code,
                f.type_facture_code, f.regime_code or "", str(f.regime_taux or ""),
                f.facture_date_soins.isoformat(), f.dossier_numero or "",
                f.centre_sante_type_code or "", f.centre_sante_type_libelle or "",
                f.date_creation.isoformat(),
            ] for f in factures],
        )

        # ── Prestations ─────────────────────────────────────────────
        prestations = list((await session.execute(
            _restreindre(select(InvoiceProvision), InvoiceProvision, debut, fin, simulation_id)
        )).scalars())
        fichiers_csv["prestations.csv"] = _csv_bytes(
            ["facture_numero", "prestation_code", "professionnel_code",
             "statut_remboursement", "montant_depense", "montant_rembourse",
             "montant_complementaire", "montant_remise", "montant_assure"],
            [[
                p.facture_numero, p.prestation_code, p.professionnel_sante_code or "",
                p.statut_remboursement or "",
                str(p.prestation_montant_depense or 0),
                str(p.prestation_montant_rq or 0),
                str(p.prestation_montant_complementaire or 0),
                str(p.prestation_montant_remise or 0),
                str(p.prestation_montant_assure or 0),
            ] for p in prestations],
        )

        # ── Ententes préalables ──────────────────────────────────────
        ententes = list((await session.execute(
            _restreindre(select(PriorAuthorization), PriorAuthorization, debut, fin, simulation_id)
        )).scalars())
        fichiers_csv["ententes_prealables.csv"] = _csv_bytes(
            ["numero_entente", "centre_sante_code", "assure_uuid",
             "dossier_numero", "type_demande", "date_debut", "facture_liee"],
            [[
                e.entente_prealable_numero, e.centre_sante_code, str(e.personne_uuid),
                e.dossier_numero or "", e.type_demande_code or "",
                e.entente_prealable_date_debut.isoformat(), e.facture_numero or "",
            ] for e in ententes],
        )

        # ── Journal technique ────────────────────────────────────────
        evenements = list((await session.execute(
            _restreindre(select(EventJournal), EventJournal, debut, fin, simulation_id)
            .order_by(EventJournal.simulated_at).limit(2000)
        )).scalars())
        fichiers_csv["journal_technique.csv"] = _csv_bytes(
            ["type_evenement", "passage_id", "horodatage_simule"],
            [[
                ev.type_evenement, ev.passage_id, ev.simulated_at.isoformat(),
            ] for ev in evenements],
        )

    # ── Assemblage du ZIP ────────────────────────────────────────────
    chemin = OUTPUT_DIR / f"{nom_fichier}.csv.zip"
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in fichiers_csv.items():
            archive.writestr(nom, contenu)

    return chemin
