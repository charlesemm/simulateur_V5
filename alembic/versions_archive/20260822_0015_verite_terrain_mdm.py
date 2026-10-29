"""Ajoute la vérité terrain du rapprochement d'identités.

Revision ID: 20260822_0015
Revises: 20260822_0014
Create Date: 2026-08-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision = "20260822_0015"
down_revision = "20260822_0014"
branch_labels = None
depends_on = None

TABLE = "TB_MDM_PAIRES"


def upgrade() -> None:
    """Crée la table des paires, avec la réponse attendue pour chacune.

    Aucune clé étrangère vers les assurés : une paire doit survivre à la purge
    des lignes d'une exécution, sinon la vérité terrain disparaîtrait avec ce
    qu'elle sert à évaluer.
    """

    if inspect(op.get_bind()).has_table(TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("PAIRE_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("SIMULATION_ID", PostgreSQLUUID(as_uuid=True)),
        sa.Column("PERSONNE_UUID_SOURCE", PostgreSQLUUID(as_uuid=True), nullable=False),
        sa.Column("PERSONNE_UUID_VARIANTE", PostgreSQLUUID(as_uuid=True), nullable=False),
        sa.Column("TYPE_VARIATION", sa.String(40), nullable=False),
        sa.Column("MEME_PERSONNE", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("COMMENTAIRE", sa.String(255)),
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
    )
    op.create_index("IX_MDM_PAIRES_SIMULATION", TABLE, ["SIMULATION_ID"])
    op.create_index("IX_MDM_PAIRES_SOURCE", TABLE, ["PERSONNE_UUID_SOURCE"])


def downgrade() -> None:
    """Retire la table des paires."""

    if inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
