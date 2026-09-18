"""M6 — Ajoute l'historique des échanges d'une campagne avec l'outil testé.

Revision ID: 20260907_0022
Revises: 20260831_0021
Create Date: 2026-09-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID

CAMPAGNES = "TB_CAMPAGNES"
ECHANGES = "TB_CAMPAGNES_ECHANGES"

revision = "20260907_0022"
down_revision = "20260831_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crée la table des échanges : une ligne par transmission, jamais écrasée.

    Table à part plutôt que des colonnes sur la campagne : une campagne peut
    être transmise plusieurs fois, à des adresses différentes — le banc
    d'essai de M8 comparera justement plusieurs outils sur la même campagne.
    Écraser la dernière tentative effacerait cette comparaison.
    """

    inspecteur = inspect(op.get_bind())
    if inspecteur.has_table(ECHANGES):
        return

    op.create_table(
        ECHANGES,
        sa.Column("ECHANGE_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("CAMPAGNE_ID", PostgreSQLUUID(as_uuid=True), nullable=False),
        sa.Column("ECHANGE_ADRESSE", sa.String(500), nullable=False),
        sa.Column("ECHANGE_DATE_ENVOI", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ECHANGE_DATE_RECEPTION", sa.DateTime(timezone=True)),
        sa.Column("ECHANGE_RESULTAT", sa.String(20), nullable=False),
        sa.Column("ECHANGE_MOTIF_ECHEC", sa.String(30)),
        sa.Column("ECHANGE_NOMBRE_CONSTATS", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("ECHANGE_MESSAGE", sa.Text),
        sa.Column("ECHANGE_RAPPORT", JSONB),
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
        sa.ForeignKeyConstraint(
            ["CAMPAGNE_ID"], [f"{CAMPAGNES}.CAMPAGNE_ID"],
            name="fk_echanges_campagne", ondelete="CASCADE",
        ),
    )
    op.create_index("IX_ECHANGES_CAMPAGNE", ECHANGES, ["CAMPAGNE_ID"])


def downgrade() -> None:
    """Retire l'historique des échanges."""

    inspecteur = inspect(op.get_bind())
    if inspecteur.has_table(ECHANGES):
        op.drop_table(ECHANGES)
