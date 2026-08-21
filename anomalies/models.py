"""Modèle SQLAlchemy de la table de configuration des anomalies."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Boolean, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AnomaliesConfigRow(Base):
    """Persiste la configuration du chaos testing entre deux démarrages.

    Ce modèle partage le Base déclaratif commun mais n'est volontairement pas
    exporté par app/models/__init__.py : la migration 0001 appelle
    Base.metadata.create_all() et créerait sinon la table en double avec la
    migration 0005. Même procédé que auth/models.py et events/models.py.
    """

    __tablename__ = "TB_CONFIG_ANOMALIES"

    config_id: Mapped[int] = mapped_column(
        "CONFIG_ID", Integer, primary_key=True, autoincrement=True
    )
    enabled: Mapped[bool] = mapped_column(
        "ENABLED", Boolean, nullable=False, default=False
    )
    rate: Mapped[Decimal] = mapped_column(
        "RATE", Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    severity: Mapped[str] = mapped_column(
        "SEVERITY", String(20), nullable=False, default="soft"
    )
    injected_count: Mapped[int] = mapped_column(
        "INJECTED_COUNT", Integer, nullable=False, default=0
    )
    date_modification: Mapped[datetime] = mapped_column(
        "DATE_MODIFICATION",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
