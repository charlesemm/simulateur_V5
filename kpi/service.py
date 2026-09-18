"""Recalcule les KPI de la fenêtre glissante depuis PostgreSQL."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models import Invoice, InvoicePathology, Pathology, PriorAuthorization, PriorAuthorizationMedicalAct
from events.models import EventJournal

# Étendue de la fenêtre glissante, en heures de temps réel.
#
# Elle ne peut pas s'appuyer sur SIMULATED_AT : chaque passage part de l'heure
# courante et avance sa propre horloge jusqu'à trois jours en avant. Le plus
# grand SIMULATED_AT du journal se situe donc dans le futur, et une fenêtre
# ancrée dessus écartait précisément l'activité récente.
FENETRE_HEURES = 24

# asyncpg refuse au-delà de 32 767 paramètres dans une seule requête. Les
# listes d'identifiants sont donc découpées, comme le fait déjà le seed.
TAILLE_LOT = 500


async def _lignes_par_lots(
    session: AsyncSession,
    construire: Callable[[Sequence[Any]], Select],
    valeurs: Iterable[Any],
) -> list[Any]:
    """Exécute une requête « IN (...) » par lots et concatène les résultats."""

    valeurs = list(valeurs)
    if not valeurs:
        return []
    lignes: list[Any] = []
    for debut in range(0, len(valeurs), TAILLE_LOT):
        lot = valeurs[debut:debut + TAILLE_LOT]
        lignes.extend((await session.execute(construire(lot))).all())
    return lignes


class KpiService:
    """Produit un snapshot JSON cohérent à partir du journal et des tables CMU."""

    async def calculate_snapshot(self) -> dict:
        """Recalcule tous les indicateurs sur les dernières heures d'activité.

        La fenêtre glisse sur DATE_CREATION, l'instant réel d'enregistrement :
        c'est la seule horloge partagée par tous les passages. Quand le moteur
        s'arrête, la fenêtre se vide d'elle-même, ce qui est le comportement
        attendu d'un indicateur temps réel.
        """

        fin = datetime.now(timezone.utc)
        cutoff = fin - timedelta(hours=FENETRE_HEURES)

        async with async_session_factory() as session:
            # Seules trois colonnes sont utiles : charger l'entité complète
            # ferait transiter tout le journal à chaque recalcul.
            events = (await session.execute(
                select(
                    EventJournal.type_evenement,
                    EventJournal.payload,
                    EventJournal.simulated_at,
                )
                .where(EventJournal.date_creation >= cutoff)
                .order_by(EventJournal.date_creation)
            )).all()

            created = {e.payload.get("facture_numero") for e in events if e.type_evenement == "facture.creee"}
            created.discard(None)
            closed = {e.payload.get("facture_numero") for e in events
                      if e.type_evenement == "facture.statut" and e.payload.get("statut") == "cloturee"}
            active = created - closed

            invoices = await _lignes_par_lots(
                session,
                lambda lot: select(
                    Invoice.facture_numero, Invoice.centre_sante_code, Invoice.type_facture_code
                ).where(Invoice.facture_numero.in_(lot)),
                created,
            )
            invoice_center = {row.facture_numero: row.centre_sante_code for row in invoices}

            # « pharmacie » est déjà pris par le compte de retraits ci-dessous :
            # une facture PHA porte son propre libellé pour ne pas les confondre.
            type_labels = {"AMB": "ambulatoire", "DEN": "dentaire",
                           "BIO": "biologie/imagerie", "HOS": "hospitalisation",
                           "PHA": "pharmacie (facture)"}
            act_counts = Counter(type_labels.get(row.type_facture_code, row.type_facture_code) for row in invoices)
            act_counts["pharmacie"] += sum(e.type_evenement == "medicament.retire" for e in events)

            treated = [e for e in events if e.type_evenement == "entente.traitee"]
            agreement_ids = [e.payload.get("entente_id") for e in treated if e.payload.get("entente_id")]

            agreements = await _lignes_par_lots(
                session,
                lambda lot: select(
                    PriorAuthorization.entente_prealable_id, PriorAuthorization.centre_sante_code
                ).where(PriorAuthorization.entente_prealable_id.in_(lot)),
                agreement_ids,
            )
            agreement_center = {row.entente_prealable_id: row.centre_sante_code for row in agreements}
            agreement_status = Counter(e.payload.get("statut") for e in treated)
            by_center: dict[str, Counter] = defaultdict(Counter)
            for event in treated:
                by_center[agreement_center.get(event.payload.get("entente_id"), "inconnu")][event.payload.get("statut")] += 1

            manual_delays = [e.payload["delai_secondes"] for e in treated
                             if e.payload.get("statut") != "validee_office" and "delai_secondes" in e.payload]
            automatic_delays = [e.payload["delai_secondes"] for e in treated
                                if e.payload.get("statut") == "validee_office" and "delai_secondes" in e.payload]

            acts = await _lignes_par_lots(
                session,
                lambda lot: select(
                    PriorAuthorizationMedicalAct.entente_prealable_id,
                    PriorAuthorizationMedicalAct.acte_medical_code,
                    PriorAuthorizationMedicalAct.acte_medical_montant_cmu,
                    PriorAuthorizationMedicalAct.acte_medical_montant_assure,
                ).where(PriorAuthorizationMedicalAct.entente_prealable_id.in_(lot)),
                agreement_ids,
            )
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

            pathology_rows = await _lignes_par_lots(
                session,
                lambda lot: select(Pathology.pathologie_code, Pathology.pathologie_denomination)
                .join(InvoicePathology,
                      (InvoicePathology.pathologie_code == Pathology.pathologie_code)
                      & (InvoicePathology.pathologie_date_debut == Pathology.pathologie_date_debut))
                .where(InvoicePathology.facture_numero.in_(lot)),
                created,
            )
            pathology_counts = Counter((code, label) for code, label in pathology_rows)
            active_by_center = Counter(invoice_center[number] for number in active if number in invoice_center)

        total_acts = sum(act_counts.values()) or 1
        total_agreements = sum(agreement_status.values()) or 1
        return {
            "generated_at": fin.isoformat(),
            "window": {"hours": FENETRE_HEURES, "from": cutoff.isoformat(), "to": fin.isoformat()},
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
