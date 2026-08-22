"""Ouvre le registre des présentations refusées à l'accueil.

Revision ID: 20260822_0016
Revises: 20260822_0015
Create Date: 2026-08-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision = "20260822_0016"
down_revision = "20260822_0015"
branch_labels = None
depends_on = None

TABLE = "TB_REFUS_ACCUEIL"


def upgrade() -> None:
    """Crée la table des refus.

    TB_FACTURES_REJETS ne pouvait pas les accueillir : sa clé primaire exige
    un numéro de facture, et un refus survient précisément avant qu'aucune
    facture ne s'ouvre.
    """

    if inspect(op.get_bind()).has_table(TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("REFUS_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("SIMULATION_ID", PostgreSQLUUID(as_uuid=True)),
        sa.Column("PASSAGE_ID", sa.String(64), nullable=False),
        sa.Column("PERSONNE_UUID", PostgreSQLUUID(as_uuid=True), nullable=False),
        sa.Column("REFUS_DATE", sa.Date, nullable=False),
        sa.Column("REFUS_MOTIF", sa.String(40), nullable=False),
        sa.Column("REGIME_CODE", sa.String(30)),
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
        sa.ForeignKeyConstraint(
            ["PERSONNE_UUID"], ["TB_REF_ASSURES.PERSONNE_UUID"],
            name="fk_refus_accueil_assure",
        ),
        sa.ForeignKeyConstraint(
            ["SIMULATION_ID"], ["TB_SIMULATIONS.SIMULATION_ID"],
            name="fk_refus_accueil_simulation",
        ),
    )
    op.create_index("IX_REFUS_ACCUEIL_SIMULATION", TABLE, ["SIMULATION_ID"])
    op.create_index("IX_REFUS_ACCUEIL_PERSONNE", TABLE, ["PERSONNE_UUID"])


def downgrade() -> None:
    """Retire le registre des refus."""

    if inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
