"""Introduit la notion d'exécution et la propage aux lignes produites.

Revision ID: 20260821_0012
Revises: 20260821_0011
Create Date: 2026-08-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID

revision = "20260821_0012"
down_revision = "20260821_0011"
branch_labels = None
depends_on = None

TABLE_EXECUTIONS = "TB_SIMULATIONS"
COLONNE = "SIMULATION_ID"

# Toutes les tables dont le moteur écrit les lignes.
TABLES_PRODUITES = (
    "TB_FACTURES",
    "TB_FACTURES_PATHOLOGIES",
    "TB_FACTURES_PRESCRIPTIONS",
    "TB_FACTURES_PRESTATIONS",
    "TB_FACTURES_STATUTS",
    "TB_ENTENTES_PREALABLES",
    "TB_ENTENTES_PREALABLES_STATUTS",
    "TB_ENTENTES_PREALABLES_ACTES_MEDICAUX",
    "TB_ENTENTES_PREALABLES_PRESTATIONS",
    "TB_EVENEMENTS_METIER",
)


def _nom_contrainte(table: str) -> str:
    """Nomme la clé étrangère d'une table vers son exécution."""

    return f"fk_{table.lower()}_simulation"


def _nom_index(table: str) -> str:
    """Nomme l'index posé sur la colonne d'exécution d'une table."""

    return f"IX_{table[3:]}_SIMULATION"


def upgrade() -> None:
    """Crée la table des exécutions et rattache les lignes à venir.

    La colonne reste nullable : les factures, ententes et événements déjà en
    base n'ont pas d'exécution d'origine et la gardent à NULL.

    Chaque objet est vérifié séparément parce que les deux chemins d'arrivée
    diffèrent. Sur une base neuve, le create_all() de la migration 0001 a déjà
    créé la colonne, portée par SimulationScopedMixin, mais ni la clé étrangère
    ni l'index ; sur une base existante, rien n'est encore là.
    """

    inspecteur = inspect(op.get_bind())

    if not inspecteur.has_table(TABLE_EXECUTIONS):
        op.create_table(
            TABLE_EXECUTIONS,
            sa.Column("SIMULATION_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
            sa.Column("SIMULATION_LIBELLE", sa.String(150), nullable=False),
            sa.Column("SIMULATION_STATUT", sa.String(20), nullable=False),
            sa.Column("SIMULATION_PARAMETRES", JSONB, nullable=False),
            sa.Column("SIMULATION_DATE_DEBUT", sa.DateTime(timezone=True), nullable=False),
            sa.Column("SIMULATION_DATE_FIN", sa.DateTime(timezone=True)),
            sa.Column("UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True)),
            sa.Column("PASSAGES_REUSSIS", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("PASSAGES_ECHOUES", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
            sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
        )

    inspecteur = inspect(op.get_bind())
    if "IX_SIMULATIONS_DATE_DEBUT" not in {
        index["name"] for index in inspecteur.get_indexes(TABLE_EXECUTIONS)
    }:
        op.create_index("IX_SIMULATIONS_DATE_DEBUT", TABLE_EXECUTIONS, ["SIMULATION_DATE_DEBUT"])

    for table in TABLES_PRODUITES:
        inspecteur = inspect(op.get_bind())

        if COLONNE not in {colonne["name"] for colonne in inspecteur.get_columns(table)}:
            op.add_column(table, sa.Column(COLONNE, PostgreSQLUUID(as_uuid=True), nullable=True))

        if _nom_contrainte(table) not in {
            cle["name"] for cle in inspecteur.get_foreign_keys(table)
        }:
            op.create_foreign_key(
                _nom_contrainte(table), table, TABLE_EXECUTIONS,
                [COLONNE], ["SIMULATION_ID"],
            )

        if _nom_index(table) not in {index["name"] for index in inspecteur.get_indexes(table)}:
            op.create_index(_nom_index(table), table, [COLONNE])


def downgrade() -> None:
    """Retire les colonnes, puis la table des exécutions."""

    for table in TABLES_PRODUITES:
        inspecteur = inspect(op.get_bind())
        if COLONNE not in {colonne["name"] for colonne in inspecteur.get_columns(table)}:
            continue
        if _nom_index(table) in {index["name"] for index in inspecteur.get_indexes(table)}:
            op.drop_index(_nom_index(table), table_name=table)
        if _nom_contrainte(table) in {cle["name"] for cle in inspecteur.get_foreign_keys(table)}:
            op.drop_constraint(_nom_contrainte(table), table, type_="foreignkey")
        op.drop_column(table, COLONNE)

    if inspect(op.get_bind()).has_table(TABLE_EXECUTIONS):
        op.drop_table(TABLE_EXECUTIONS)
