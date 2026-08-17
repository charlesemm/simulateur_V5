from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from app.database import async_session_factory
from app.models import PriorAuthorizationMedicalAct
from api.schema import Granularity, KpiName
from events.models import EventJournal

def bucket_start(value: datetime, granularity: Granularity) -> datetime:
    """Arrondit un horodatage au début de la granularité demandée."""

    if granularity == Granularity.minute:
        return value.replace(second=0, microsecond=0)
    if granularity == Granularity.heure:
        return value.replace(minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)

async def calculate_history(kpi_name: KpiName, since: datetime,
                            granularity: Granularity) -> list[dict]:
    """Agrège les événements dans des buckets ordonnés."""

    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    async with async_session_factory() as session:
        events = list((await session.execute(
            select(EventJournal).where(EventJournal.simulated_at >= since)
            .order_by(EventJournal.simulated_at)
        )).scalars())
        buckets: dict[datetime, Decimal] = defaultdict(Decimal)
        if kpi_name == KpiName.passages:
            for event in events:
                if event.type_evenement == "facture.creee":
                    buckets[bucket_start(event.simulated_at, granularity)] += 1
        elif kpi_name == KpiName.ententes_acceptees:
            for event in events:
                if event.type_evenement == "entente.traitee" and event.payload.get("statut") in {"acceptee", "validee_office"}:
                    buckets[bucket_start(event.simulated_at, granularity)] += 1
        else:
            treated = {event.payload.get("entente_id"): event for event in events
                       if event.type_evenement == "entente.traitee"}
            ids = [value for value in treated if value is not None]
            acts = list((await session.execute(
                select(PriorAuthorizationMedicalAct).where(
                    PriorAuthorizationMedicalAct.entente_prealable_id.in_(ids)
                )
            )).scalars()) if ids else []
            for act in acts:
                event = treated[act.entente_prealable_id]
                amount = (act.acte_medical_montant_cmu if kpi_name == KpiName.montant_cmu
                          else act.acte_medical_montant_assure) or Decimal(0)
                buckets[bucket_start(event.simulated_at, granularity)] += amount
    return [{"timestamp": timestamp, "value": float(value)}
            for timestamp, value in sorted(buckets.items())]

