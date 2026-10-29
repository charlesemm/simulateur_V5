"""Ajoute la table des utilisateurs et de leurs rôles.

Revision ID: 20260814_0004
Revises: 20260814_0003
Create Date: 2026-08-18
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision = "20260814_0004"
down_revision = "20260814_0003"
branch_labels = None
depends_on = None


def _table_existe(nom: str) -> bool:
    """Indique si la table est déjà présente sur la base.

    La révision 0001 appelle Base.metadata.create_all() : sur une base neuve,
    elle a déjà créé cette table telle que le modèle la déclare aujourd'hui.
    La création ci-dessous est donc conditionnée à son absence réelle, pour
    que la chaîne rejoue aussi bien depuis zéro que sur une base ancienne.
    """

    return nom in set(inspect(op.get_bind()).get_table_names())

def upgrade() -> None:
    if _table_existe("TB_UTILISATEURS"):
        return

    op.create_table(
        "TB_UTILISATEURS",
        sa.Column("UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("EMAIL", sa.String(150), nullable=False, unique=True),
        sa.Column("MOT_DE_PASSE_HASH", sa.String(255), nullable=False),
        sa.Column("NOM_COMPLET", sa.String(150), nullable=False),
        sa.Column("ROLE", sa.String(20), nullable=False),
        sa.Column("STATUT_ACTIF", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("DERNIERE_CONNEXION", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("DATE_CREATION", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100), nullable=True),
        sa.Column("DATE_MODIFICATION", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100), nullable=True),
        sa.CheckConstraint(
            "\"ROLE\" IN ('administrateur', 'operateur', 'observateur')",
            name="ck_utilisateurs_role_valide",
        ),
    )
    op.create_index("ix_utilisateurs_email", "TB_UTILISATEURS", ["EMAIL"])


def downgrade() -> None:
    op.drop_index("ix_utilisateurs_email", table_name="TB_UTILISATEURS")
    op.drop_table("TB_UTILISATEURS")