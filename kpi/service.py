"""Recalcule les KPI de la fenêtre glissante depuis PostgreSQL."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from app.database import async_session_factory
from app.models import Invoice, InvoicePathology, Pathology, PriorAuthorization, PriorAuthorizationMedicalAct
from events.models import EventJournal

class KpiService:
    """Produit un snapshot JSON cohérent à partir du journal et des tables CMU."""

    async def calculate_snapshot(self) -> dict:
        """Recalcule tous les indicateurs sur les dernières 24 h simulées."""

        async with async_session_factory() as session:
            latest = (await session.execute(
                select(EventJournal.simulated_at).order_by(EventJournal.simulated_at.desc()).limit(1)
            )).scalar_one_or_none() or datetime.now(timezone.utc)
            cutoff = latest - timedelta(hours=24)
            events = list((await session.execute(
                select(EventJournal).where(EventJournal.simulated_at >= cutoff)
                .order_by(EventJournal.simulated_at)
            )).scalars())

            created = {e.payload.get("facture_numero") for e in events if e.type_evenement == "facture.creee"}
            created.discard(None)
            closed = {e.payload.get("facture_numero") for e in events
                      if e.type_evenement == "facture.statut" and e.payload.get("statut") == "cloturee"}
            active = created - closed
            invoices = list((await session.execute(
                select(Invoice).where(Invoice.facture_numero.in_(created))
            )).scalars()) if created else []
            invoice_center = {row.facture_numero: row.centre_sante_code for row in invoices}

            type_labels = {"AMB": "ambulatoire", "DEN": "dentaire"}
            act_counts = Counter(type_labels.get(row.type_facture_code, row.type_facture_code) for row in invoices)
            act_counts["pharmacie"] += sum(e.type_evenement == "medicament.retire" for e in events)

            treated = [e for e in events if e.type_evenement == "entente.traitee"]
            agreement_ids = [e.payload.get("entente_id") for e in treated if e.payload.get("entente_id")]
            agreements = list((await session.execute(
                select(PriorAuthorization).where(PriorAuthorization.entente_prealable_id.in_(agreement_ids))
            )).scalars()) if agreement_ids else []
            agreement_center = {row.entente_prealable_id: row.centre_sante_code for row in agreements}
            agreement_status = Counter(e.payload.get("statut") for e in treated)
            by_center: dict[str, Counter] = defaultdict(Counter)
            for event in treated:
                by_center[agreement_center.get(event.payload.get("entente_id"), "inconnu")][event.payload.get("statut")] += 1

            manual_delays = [e.payload["delai_secondes"] for e in treated if e.payload.get("statut") != "validee_office"]
            automatic_delays = [e.payload["delai_secondes"] for e in treated if e.payload.get("statut") == "validee_office"]

            acts = list((await session.execute(
                select(PriorAuthorizationMedicalAct).where(
                    PriorAuthorizationMedicalAct.entente_prealable_id.in_(agreement_ids)
                )
            )).scalars()) if agreement_ids else []
            for row in acts:
                category = (
                    "hospitalisation"
                    if row.acte_medical_code.startswith("HOS-")
                    else "biologie-imagerie"
                )
                act_counts[category] += 1
            total_cmu = sum((row.acte_medical_montant_cmu or Decimal(0)) for row in acts)
            total_insured = sum((row.acte_medical_montant_assure or Decimal(0)) for row in acts)
            amounts_by_center: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"cmu": Decimal(0), "assure": Decimal(0)})
            for row in acts:
                center = agreement_center.get(row.entente_prealable_id, "inconnu")
                amounts_by_center[center]["cmu"] += row.acte_medical_montant_cmu or Decimal(0)
                amounts_by_center[center]["assure"] += row.acte_medical_montant_assure or Decimal(0)

            pathology_rows = (await session.execute(
                select(Pathology.pathologie_code, Pathology.pathologie_denomination)
                .join(InvoicePathology,
                      (InvoicePathology.pathologie_code == Pathology.pathologie_code)
                      & (InvoicePathology.pathologie_date_debut == Pathology.pathologie_date_debut))
                .where(InvoicePathology.facture_numero.in_(created))
            )).all() if created else []
            pathology_counts = Counter((code, label) for code, label in pathology_rows)
            active_by_center = Counter(invoice_center[number] for number in active if number in invoice_center)

        total_acts = sum(act_counts.values()) or 1
        total_agreements = sum(agreement_status.values()) or 1
        return {
            "generated_at": latest.isoformat(),
            "window": {"hours": 24, "from": cutoff.isoformat(), "to": latest.isoformat()},
            "passages": {"en_cours": len(active), "clotures": len(closed), "total": len(created)},
            "actes_repartition": [
                {"type": key, "nombre": value, "pourcentage": round(value * 100 / total_acts, 2)}
                for key, value in sorted(act_counts.items())
            ],
            "ententes": {
                "global": {key: {"nombre": value, "pourcentage": round(value * 100 / total_agreements, 2)}
                           for key, value in agreement_status.items()},
                "par_centre": {center: dict(values) for center, values in by_center.items()},
                "delai_moyen_secondes": {
                    "medecin_conseil": round(sum(manual_delays) / len(manual_delays), 2) if manual_delays else None,
                    "validation_office": round(sum(automatic_delays) / len(automatic_delays), 2) if automatic_delays else None,
                },
            },
            "montants": {
                "cumule": {"cmu": float(total_cmu), "assure": float(total_insured)},
                "par_centre": {center: {key: float(value) for key, value in amounts.items()}
                               for center, amounts in amounts_by_center.items()},
            },
            "top_pathologies": [
                {"code": code, "libelle": label, "nombre": count}
                for (code, label), count in pathology_counts.most_common(5)
            ],
            "charge_centres": [
                {"centre_sante_code": center, "passages_actifs": count}
                for center, count in sorted(active_by_center.items())
            ],
        }