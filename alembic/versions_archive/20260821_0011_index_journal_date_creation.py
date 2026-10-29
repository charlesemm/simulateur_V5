"""Indexe le journal sur sa date d'enregistrement réelle.

Revision ID: 20260821_0011
Revises: 20260821_0010
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "20260821_0011"
down_revision = "20260821_0010"
branch_labels = None
depends_on = None

TABLE = "TB_EVENEMENTS_METIER"
INDEX = "IX_EVENEMENTS_DATE_CREATION"


def _index_existe() -> bool:
    """Indique si l'index est déjà posé sur la table."""

    return INDEX in {
        index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE)
    }


def upgrade() -> None:
    """Ajoute l'index balayé par la fenêtre glissante des KPI.

    Le snapshot se recalcule jusqu'à une fois par seconde et filtre sur
    DATE_CREATION. Sans index, chaque recalcul impose un parcours complet du
    journal, dont la taille croît avec la durée de la simulation.
    """

    if not _index_existe():
        op.create_index(INDEX, TABLE, ["DATE_CREATION"])


def downgrade() -> None:
    """Retire l'index."""

    if _index_existe():
        op.drop_index(INDEX, table_name=TABLE)
