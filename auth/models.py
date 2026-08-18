"""Modèle SQLAlchemy de la table des utilisateurs."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class User(AuditMixin, Base):
    """Un compte utilisateur du dashboard, avec un rôle unique."""

    __tablename__ = "TB_UTILISATEURS"

    utilisateur_uuid: Mapped[uuid.UUID] = mapped_column(
        "UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column("EMAIL", String(150), nullable=False, unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column("MOT_DE_PASSE_HASH", String(255), nullable=False)
    nom_complet: Mapped[str] = mapped_column("NOM_COMPLET", String(150), nullable=False)
    role: Mapped[str] = mapped_column("ROLE", String(20), nullable=False)
    statut_actif: Mapped[bool] = mapped_column("STATUT_ACTIF", Boolean, nullable=False, default=True)
    derniere_connexion: Mapped[TIMESTAMP | None] = mapped_column(
        "DERNIERE_CONNEXION", TIMESTAMP(timezone=True), nullable=True
    )
