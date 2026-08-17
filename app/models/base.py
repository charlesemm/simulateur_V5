"""Définit la base déclarative et les colonnes d'audit communes."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles SQLAlchemy."""


class AuditMixin:
    """Ajoute les quatre colonnes d'audit obligatoires à une table."""

    # La valeur serveur couvre aussi les insertions effectuées hors de l'API.
    date_creation: Mapped[datetime] = mapped_column(
        "DATE_CREATION",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    utilisateur_id_creation: Mapped[str | None] = mapped_column(
        "UTILISATEUR_ID_CREATION", String(100)
    )
    date_modification: Mapped[datetime | None] = mapped_column(
        "DATE_MODIFICATION", DateTime(timezone=True)
    )
    utilisateur_id_modification: Mapped[str | None] = mapped_column(
        "UTILISATEUR_ID_MODIFICATION", String(100)
    )