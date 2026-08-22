"""Définit la base déclarative et les colonnes d'audit communes."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
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
        "DATE_MODIFICATION",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    utilisateur_id_modification: Mapped[str | None] = mapped_column(
        "UTILISATEUR_ID_MODIFICATION", String(100)
    )


class SimulationScopedMixin:
    """Rattache une ligne produite par le moteur à son exécution.

    Nullable : les lignes créées avant l'introduction de TB_SIMULATIONS n'ont
    pas d'exécution d'origine et la gardent à NULL. Un passage lancé hors API
    sans identifiant d'exécution produit lui aussi des lignes à NULL.

    L'index et la clé étrangère sont posés par la migration 0012, et non
    déclarés ici : sur une base neuve, le create_all() de la migration 0001
    crée déjà la colonne, et deux définitions concurrentes produiraient des
    index aux noms différents selon l'ancienneté de la base.
    """

    simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        "SIMULATION_ID", PostgreSQLUUID(as_uuid=True)
    )