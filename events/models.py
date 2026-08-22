"""Déclare le modèle SQLAlchemy du journal événementiel technique."""

from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import AuditMixin, Base, SimulationScopedMixin


class EventJournal(SimulationScopedMixin, AuditMixin, Base):
    """Conserve un événement métier avec son horloge simulée."""

    __tablename__ = "TB_EVENEMENTS_METIER"
    __table_args__ = (
        Index("IX_EVENEMENTS_SIMULATED_AT", "SIMULATED_AT"),
        Index("IX_EVENEMENTS_TYPE", "TYPE_EVENEMENT"),
        Index("IX_EVENEMENTS_PASSAGE", "PASSAGE_ID"),
        # La fenêtre glissante des KPI balaie DATE_CREATION une fois par
        # seconde : sans index, chaque recalcul relit tout le journal.
        Index("IX_EVENEMENTS_DATE_CREATION", "DATE_CREATION"),
    )

    evenement_id: Mapped[UUID] = mapped_column("EVENEMENT_ID", PostgreSQLUUID(as_uuid=True), primary_key=True)
    type_evenement: Mapped[str] = mapped_column("TYPE_EVENEMENT", String(80), nullable=False)
    passage_id: Mapped[str] = mapped_column("PASSAGE_ID", String(64), nullable=False)
    simulated_at: Mapped[datetime] = mapped_column("SIMULATED_AT", DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column("PAYLOAD", JSONB, nullable=False)