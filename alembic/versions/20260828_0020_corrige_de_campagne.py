"""Ajoute le corrigé des campagnes et ce que la génération laisse derrière.

Revision ID: 20260828_0020
Revises: 20260828_0019
Create Date: 2026-08-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision = "20260828_0020"
down_revision = "20260828_0019"
branch_labels = None
depends_on = None

CAMPAGNES = "TB_CAMPAGNES"
CORRIGE = "TB_CAMPAGNES_CORRIGE"

# Ce que la génération inscrit sur la campagne elle-même.
COLONNES_GENERATION = (
    ("CAMPAGNE_DATE_GENERATION", sa.DateTime(timezone=True), None),
    ("CAMPAGNE_LIGNES_GENEREES", sa.Integer, "0"),
    ("CAMPAGNE_ANOMALIES_POSEES", sa.Integer, "0"),
    ("CAMPAGNE_EMPREINTE", sa.String(64), None),
    ("CAMPAGNE_FICHIER", sa.String(255), None),
)


def upgrade() -> None:
    """Crée le corrigé et les colonnes de génération.

    Le corrigé est une table à part et non un champ JSON de la campagne : il se
    compte, se filtre par type d'anomalie et se rapproche ligne à ligne du
    rapport de l'outil testé — trois choses qu'un document imbriqué rendrait
    coûteuses dès le premier palier sérieux.
    """

    inspecteur = inspect(op.get_bind())
    existantes = {colonne["name"] for colonne in inspecteur.get_columns(CAMPAGNES)}

    for nom, type_sql, defaut in COLONNES_GENERATION:
        if nom in existantes:
            continue
        op.add_column(
            CAMPAGNES,
            sa.Column(
                nom, type_sql,
                # Une colonne sans valeur par défaut décrit ce que la
                # génération produira : elle est nulle tant qu'elle n'a pas
                # eu lieu. Les compteurs, eux, partent à zéro.
                nullable=defaut is None,
                server_default=sa.text(defaut) if defaut else None,
            ),
        )

    if inspecteur.has_table(CORRIGE):
        return

    op.create_table(
        CORRIGE,
        sa.Column("CAMPAGNE_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("CORRIGE_LIGNE", sa.Integer, primary_key=True),
        sa.Column("ANOMALIE_CODE", sa.String(50), primary_key=True),
        sa.Column("CORRIGE_CHAMP", sa.String(60), nullable=False),
        sa.Column("CORRIGE_VALEUR_ORIGINE", sa.Text, nullable=False),
        sa.Column("CORRIGE_VALEUR_INJECTEE", sa.Text, nullable=False),
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
        sa.ForeignKeyConstraint(
            ["CAMPAGNE_ID"], [f"{CAMPAGNES}.CAMPAGNE_ID"],
            name="fk_corrige_campagne", ondelete="CASCADE",
        ),
    )
    op.create_index("IX_CORRIGE_CAMPAGNE", CORRIGE, ["CAMPAGNE_ID"])
    op.create_index("IX_CORRIGE_ANOMALIE", CORRIGE, ["CAMPAGNE_ID", "ANOMALIE_CODE"])


def downgrade() -> None:
    """Retire le corrigé et les colonnes de génération."""

    inspecteur = inspect(op.get_bind())
    if inspecteur.has_table(CORRIGE):
        op.drop_table(CORRIGE)

    existantes = {colonne["name"] for colonne in inspecteur.get_columns(CAMPAGNES)}
    for nom, _type, _defaut in COLONNES_GENERATION:
        if nom in existantes:
            op.drop_column(CAMPAGNES, nom)
