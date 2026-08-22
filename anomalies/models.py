"""Modèles SQLAlchemy du réglage, du catalogue et du journal des anomalies."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    TIMESTAMP, Boolean, ForeignKey, Index, Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


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


class AnomalyType(AuditMixin, Base):
    """Un type d'anomalie du catalogue, avec son propre interrupteur.

    L'interrupteur global de TB_CONFIG_ANOMALIES reste au-dessus : un type
    n'est injecté que si les deux sont ouverts. Le taux, lui, est propre au
    type — c'est ce qui permet de demander des montants aberrants sans
    demander des dates antidatées.
    """

    __tablename__ = "TB_REF_ANOMALIES"

    anomalie_code: Mapped[str] = mapped_column("ANOMALIE_CODE", String(40), primary_key=True)
    anomalie_libelle: Mapped[str] = mapped_column("ANOMALIE_LIBELLE", String(150), nullable=False)
    # Famille et couleur : ce qui regroupe les types en boutons dans la console.
    anomalie_famille: Mapped[str] = mapped_column("ANOMALIE_FAMILLE", String(40), nullable=False)
    anomalie_couleur: Mapped[str] = mapped_column("ANOMALIE_COULEUR", String(9), nullable=False)
    anomalie_table_cible: Mapped[str] = mapped_column("ANOMALIE_TABLE_CIBLE", String(80), nullable=False)
    anomalie_colonne_cible: Mapped[str] = mapped_column("ANOMALIE_COLONNE_CIBLE", String(80), nullable=False)
    anomalie_severite: Mapped[str] = mapped_column("ANOMALIE_SEVERITE", String(20), nullable=False)
    anomalie_active: Mapped[bool] = mapped_column("ANOMALIE_ACTIVE", Boolean, nullable=False, default=True)
    anomalie_taux: Mapped[Decimal] = mapped_column(
        "ANOMALIE_TAUX", Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    # Moment d'entrée en scène : continu, demarrage, differe ou manuel.
    anomalie_declenchement: Mapped[str] = mapped_column(
        "ANOMALIE_DECLENCHEMENT", String(20), nullable=False, default="continu"
    )
    # Fenêtre initiale pour « demarrage », attente pour « differe », en secondes.
    anomalie_delai_secondes: Mapped[int | None] = mapped_column(
        "ANOMALIE_DELAI_SECONDES", Integer
    )


class AnomalyInjection(AuditMixin, Base):
    """Une anomalie réellement injectée, et ce qu'elle a remplacé.

    C'est la vérité terrain : le moteur de qualité des données et le MDM se
    mesurent en comparant ce qu'ils détectent à ce qui est consigné ici. La
    valeur d'origine est conservée pour que l'écart soit mesurable, et non
    seulement constatable.
    """

    __tablename__ = "TB_ANOMALIES_INJECTIONS"
    __table_args__ = (
        Index("IX_ANOMALIES_INJECTIONS_SIMULATION", "SIMULATION_ID"),
        Index("IX_ANOMALIES_INJECTIONS_CODE", "ANOMALIE_CODE"),
    )

    injection_id: Mapped[uuid.UUID] = mapped_column(
        "INJECTION_ID", PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    anomalie_code: Mapped[str] = mapped_column(
        "ANOMALIE_CODE", String(40), ForeignKey("TB_REF_ANOMALIES.ANOMALIE_CODE"), nullable=False
    )
    # Nuls pour les anomalies posées par le seed, qui corrompt le référentiel
    # avant qu'aucune exécution n'existe.
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        "SIMULATION_ID", PostgreSQLUUID(as_uuid=True)
    )
    passage_id: Mapped[str | None] = mapped_column("PASSAGE_ID", String(64))
    # Clé métier de la ligne corrompue, telle qu'elle se lit dans sa table.
    cible_cle: Mapped[str | None] = mapped_column("CIBLE_CLE", String(100))
    valeur_origine: Mapped[str | None] = mapped_column("VALEUR_ORIGINE", Text)
    valeur_injectee: Mapped[str | None] = mapped_column("VALEUR_INJECTEE", Text)
