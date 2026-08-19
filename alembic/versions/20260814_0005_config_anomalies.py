"""Ajoute la table de persistance de la configuration des anomalies (Chaos Testing).

Revision ID: 20260814_0005
Revises: 20260814_0004
Create Date: 2026-08-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Identifiants de révision Alembic
revision = "20260814_0005"
down_revision = "20260814_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Création de la table de configuration des anomalies si besoin de persistance
    op.create_table(
        "TB_CONFIG_ANOMALIES",
        sa.Column("CONFIG_ID", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ENABLED", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("RATE", sa.Numeric(3, 2), nullable=False, server_default="0.0"),
        sa.Column("SEVERITY", sa.String(20), nullable=False, server_default="soft"),
        sa.Column("INJECTED_COUNT", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("DATE_MODIFICATION", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("TB_CONFIG_ANOMALIES")
