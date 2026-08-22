"""Modèle SQLAlchemy de la vérité terrain du rapprochement d'identités."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class MdmPair(AuditMixin, Base):
    """Deux assurés, et la réponse : est-ce la même personne ?

    C'est la pièce qu'aucune donnée réelle ne fournit. Sur un référentiel de
    production, personne ne sait dire combien de doublons ont échappé au
    rapprochement — ici, si.

    Non exporté par app/models/__init__.py, comme anomalies/models.py : le
    create_all() de la migration 0001 créerait sinon la table en double.
    """

    __tablename__ = "TB_MDM_PAIRES"
    __table_args__ = (
        Index("IX_MDM_PAIRES_SIMULATION", "SIMULATION_ID"),
        Index("IX_MDM_PAIRES_SOURCE", "PERSONNE_UUID_SOURCE"),
    )

    paire_id: Mapped[uuid.UUID] = mapped_column(
        "PAIRE_ID", PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Nul pour une paire produite hors exécution.
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        "SIMULATION_ID", PostgreSQLUUID(as_uuid=True)
    )
    personne_uuid_source: Mapped[uuid.UUID] = mapped_column(
        "PERSONNE_UUID_SOURCE", PostgreSQLUUID(as_uuid=True), nullable=False
    )
    personne_uuid_variante: Mapped[uuid.UUID] = mapped_column(
        "PERSONNE_UUID_VARIANTE", PostgreSQLUUID(as_uuid=True), nullable=False
    )
    type_variation: Mapped[str] = mapped_column(
        "TYPE_VARIATION", String(40), nullable=False
    )
    # La réponse attendue. Fausse pour les leurres : deux personnes qui se
    # ressemblent sans être la même, sans quoi un moteur qui rapproche tout
    # obtiendrait un rappel parfait.
    meme_personne: Mapped[bool] = mapped_column(
        "MEME_PERSONNE", Boolean, nullable=False, default=True
    )
    commentaire: Mapped[str | None] = mapped_column("COMMENTAIRE", String(255))
