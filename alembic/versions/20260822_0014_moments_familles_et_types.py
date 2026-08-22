"""Ajoute le moment d'injection, les familles d'anomalies et le type de run.

Revision ID: 20260822_0014
Revises: 20260822_0013
Create Date: 2026-08-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

from anomalies.catalogue import CATALOGUE_INITIAL, DECLENCHEMENT_CONTINU

revision = "20260822_0014"
down_revision = "20260822_0013"
branch_labels = None
depends_on = None

TABLE_CATALOGUE = "TB_REF_ANOMALIES"
TABLE_EXECUTIONS = "TB_SIMULATIONS"

# Colonnes ajoutées au catalogue : la famille et sa couleur regroupent les
# types en boutons, le déclenchement dit quand le type entre en scène.
COLONNES_CATALOGUE = (
    ("ANOMALIE_FAMILLE", sa.String(40), sa.text("'REFERENTIEL'")),
    ("ANOMALIE_COULEUR", sa.String(9), sa.text("'#a16207'")),
    ("ANOMALIE_DECLENCHEMENT", sa.String(20), sa.text(f"'{DECLENCHEMENT_CONTINU}'")),
)


def _colonnes(table: str) -> set[str]:
    """Retourne les colonnes réellement présentes sur une table."""

    return {colonne["name"] for colonne in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    """Complète le catalogue et les exécutions, sans rien casser d'existant.

    Les colonnes de famille arrivent avec un défaut, puis chaque type reçoit
    la sienne : les lignes déjà en base ne peuvent donc pas rester vides.
    """

    colonnes = _colonnes(TABLE_CATALOGUE)
    for nom, type_sql, defaut in COLONNES_CATALOGUE:
        if nom not in colonnes:
            op.add_column(
                TABLE_CATALOGUE,
                sa.Column(nom, type_sql, nullable=False, server_default=defaut),
            )

    if "ANOMALIE_DELAI_SECONDES" not in colonnes:
        op.add_column(TABLE_CATALOGUE, sa.Column("ANOMALIE_DELAI_SECONDES", sa.Integer))

    connexion = op.get_bind()
    for type_anomalie in CATALOGUE_INITIAL:
        connexion.execute(
            text(
                f'UPDATE "{TABLE_CATALOGUE}" SET "ANOMALIE_FAMILLE" = :famille, '
                '"ANOMALIE_COULEUR" = :couleur WHERE "ANOMALIE_CODE" = :code'
            ),
            {
                "famille": type_anomalie.famille,
                "couleur": type_anomalie.couleur,
                "code": type_anomalie.code,
            },
        )

    if "SIMULATION_TYPE" not in _colonnes(TABLE_EXECUTIONS):
        op.add_column(TABLE_EXECUTIONS, sa.Column("SIMULATION_TYPE", sa.String(20)))


def downgrade() -> None:
    """Retire les quatre colonnes du catalogue et le type d'exécution."""

    colonnes = _colonnes(TABLE_CATALOGUE)
    for nom in ("ANOMALIE_DELAI_SECONDES", *(nom for nom, _, _ in COLONNES_CATALOGUE)):
        if nom in colonnes:
            op.drop_column(TABLE_CATALOGUE, nom)

    if "SIMULATION_TYPE" in _colonnes(TABLE_EXECUTIONS):
        op.drop_column(TABLE_EXECUTIONS, "SIMULATION_TYPE")
