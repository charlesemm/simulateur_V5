"""Ouvre la table des campagnes de test du module Qualité des données.

Revision ID: 20260828_0019
Revises: 20260822_0018
Create Date: 2026-08-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID

revision = "20260828_0019"
down_revision = "20260822_0018"
branch_labels = None
depends_on = None

TABLE = "TB_CAMPAGNES"


def upgrade() -> None:
    """Crée la table des campagnes.

    Une campagne n'est pas une exécution du moteur : elle n'a ni vitesse ni
    passages simultanés, mais un volume, une graine, un jeu de données et une
    note. TB_SIMULATIONS ne pouvait donc pas l'accueillir sans devenir un
    fourre-tout de deux objets différents.
    """

    if inspect(op.get_bind()).has_table(TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("CAMPAGNE_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("CAMPAGNE_REFERENCE", sa.String(20), nullable=False, unique=True),
        sa.Column("CAMPAGNE_LIBELLE", sa.String(150), nullable=False),
        sa.Column("CAMPAGNE_STATUT", sa.String(30), nullable=False,
                  server_default="creee"),
        sa.Column("CAMPAGNE_GRAINE", sa.BigInteger, nullable=False),
        sa.Column("CAMPAGNE_PALIER", sa.String(20), nullable=False),
        sa.Column("CAMPAGNE_VOLUME_CIBLE", sa.Integer, nullable=False),
        sa.Column("CAMPAGNE_PARAMETRES", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("CAMPAGNE_DATE_FIN", sa.DateTime(timezone=True)),
        sa.Column("UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True)),
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
        sa.CheckConstraint(
            '"CAMPAGNE_VOLUME_CIBLE" > 0', name="ck_campagnes_volume_positif"
        ),
    )
    op.create_index("IX_CAMPAGNES_DATE_CREATION", TABLE, ["DATE_CREATION"])
    op.create_index("IX_CAMPAGNES_STATUT", TABLE, ["CAMPAGNE_STATUT"])


def downgrade() -> None:
    """Retire la table des campagnes."""

    if inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
