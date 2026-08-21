"""Reconstruit l'historique d'un KPI à partir du journal d'événements."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session_factory
from app.models import PriorAuthorizationMedicalAct
from api.schema import Granularity, KpiName
from events.models import EventJournal

# Même limite que le service KPI : asyncpg plafonne à 32 767 paramètres.
TAILLE_LOT = 500


def bucket_start(value: datetime, granularity: Granularity) -> datetime:
    """Arrondit un horodatage au début de la granularité demandée."""

    if granularity == Granularity.minute:
        return value.replace(second=0, microsecond=0)
    if granularity == Granularity.heure:
        return value.replace(minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


async def calculate_history(kpi_name: KpiName, since: datetime,
                            granularity: Granularity) -> list[dict]:
    """Agrège les événements dans des buckets ordonnés.

    Comme pour le snapshot, la borne porte sur DATE_CREATION -- l'instant réel
    d'enregistrement. SIMULATED_AT appartient à chaque passage et peut se
    situer plusieurs jours en avant, ce qui rendait l'historique illisible.
    """

    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    async with async_session_factory() as session:
        events = (await session.execute(
            select(
                EventJournal.type_evenement,
                EventJournal.payload,
                EventJournal.date_creation,
            )
            .where(EventJournal.date_creation >= since)
            .order_by(EventJournal.date_creation)
        )).all()

        buckets: dict[datetime, Decimal] = defaultdict(Decimal)
        if kpi_name == KpiName.passages:
            for event in events:
                if event.type_evenement == "facture.creee":
                    buckets[bucket_start(event.date_creation, granularity)] += 1
        elif kpi_name == KpiName.ententes_acceptees:
            for event in events:
                if event.type_evenement == "entente.traitee" and event.payload.get("statut") in {"acceptee", "validee_office"}:
                    buckets[bucket_start(event.date_creation, granularity)] += 1
        else:
            treated = {event.payload.get("entente_id"): event for event in events
                       if event.type_evenement == "entente.traitee"}
            ids = [value for value in treated if value is not None]
            acts = []
            for debut in range(0, len(ids), TAILLE_LOT):
                lot = ids[debut:debut + TAILLE_LOT]
                acts.extend((await session.execute(
                    select(
                        PriorAuthorizationMedicalAct.entente_prealable_id,
                        PriorAuthorizationMedicalAct.acte_medical_montant_cmu,
                        PriorAuthorizationMedicalAct.acte_medical_montant_assure,
                    ).where(PriorAuthorizationMedicalAct.entente_prealable_id.in_(lot))
                )).all())
            for act in acts:
                event = treated[act.entente_prealable_id]
                amount = (act.acte_medical_montant_cmu if kpi_name == KpiName.montant_cmu
                          else act.acte_medical_montant_assure) or Decimal(0)
                buckets[bucket_start(event.date_creation, granularity)] += amount

    return [{"timestamp": timestamp, "value": float(value)}
            for timestamp, value in sorted(buckets.items())]
