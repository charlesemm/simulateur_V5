"""Modèle SQLAlchemy de la table des exécutions du simulateur."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

# Statuts possibles d'une exécution, du démarrage à sa fin.
STATUT_EN_COURS = "en_cours"
STATUT_TERMINEE = "terminee"
STATUT_ARRETEE = "arretee"
STATUT_ECHOUEE = "echouee"


class SimulationRun(AuditMixin, Base):
    """Une exécution du moteur, de son démarrage à sa clôture.

    Chaque ligne produite par le moteur porte le SIMULATION_ID de l'exécution
    qui l'a créée : c'est ce qui rend possible la volumétrie par exécution, la
    purge sélective et la vérité terrain du MDM. Ce modèle n'est volontairement
    pas exporté par app/models/__init__.py, pour la même raison que
    anomalies/models.py : la migration 0001 appelle Base.metadata.create_all()
    et créerait sinon la table en double avec la migration 0012.
    """

    __tablename__ = "TB_SIMULATIONS"
    __table_args__ = (Index("IX_SIMULATIONS_DATE_DEBUT", "SIMULATION_DATE_DEBUT"),)

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        "SIMULATION_ID", PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    simulation_libelle: Mapped[str] = mapped_column(
        "SIMULATION_LIBELLE", String(150), nullable=False
    )
    simulation_statut: Mapped[str] = mapped_column(
        "SIMULATION_STATUT", String(20), nullable=False, default=STATUT_EN_COURS
    )
    # Tous les paramètres du run (vitesse, concurrence, graine) : le format
    # bougera à chaque lot, un JSONB évite une migration par paramètre ajouté.
    simulation_parametres: Mapped[dict[str, Any]] = mapped_column(
        "SIMULATION_PARAMETRES", JSONB, nullable=False
    )
    simulation_date_debut: Mapped[datetime] = mapped_column(
        "SIMULATION_DATE_DEBUT", DateTime(timezone=True), nullable=False
    )
    simulation_date_fin: Mapped[datetime | None] = mapped_column(
        "SIMULATION_DATE_FIN", DateTime(timezone=True)
    )
    # Nul quand le moteur est lancé hors de l'API (tests, script).
    utilisateur_uuid: Mapped[uuid.UUID | None] = mapped_column(
        "UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True)
    )
    passages_reussis: Mapped[int] = mapped_column(
        "PASSAGES_REUSSIS", Integer, nullable=False, default=0
    )
    passages_echoues: Mapped[int] = mapped_column(
        "PASSAGES_ECHOUES", Integer, nullable=False, default=0
    )
