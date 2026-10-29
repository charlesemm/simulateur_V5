"""Ajoute la latitude/longitude des localités (TB_REF_COLLECTIVITES).

Une localité = une position, jointe par TB_REF_CENTRES_SANTE.COLLECTIVITE_CODE
(et TB_REF_PHARMACIES) : pas de duplication des coordonnées par centre.
Colonnes nullables : les localités sans correspondance de géocodage
(seed/donnees/geocoder_localites.py -> localites_coordonnees.csv) restent
vides plutôt que d'inventer une position.

Sur une base neuve, la migration 0001 n'a pas ces colonnes (table créée en
0025) : on ne les ajoute que si elles manquent.

Revision ID: 20260914_0027
Revises: 20260911_0026
Create Date: 2026-09-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260914_0027"
down_revision = "20260911_0026"
branch_labels = None
depends_on = None

COLLECTIVITES = "TB_REF_COLLECTIVITES"
LATITUDE = "COLLECTIVITE_LATITUDE"
LONGITUDE = "COLLECTIVITE_LONGITUDE"


def _colonnes() -> set[str]:
    return {colonne["name"] for colonne in inspect(op.get_bind()).get_columns(COLLECTIVITES)}


def upgrade() -> None:
    colonnes = _colonnes()
    if LATITUDE not in colonnes:
        op.add_column(COLLECTIVITES, sa.Column(LATITUDE, sa.Numeric(9, 6)))
    if LONGITUDE not in colonnes:
        op.add_column(COLLECTIVITES, sa.Column(LONGITUDE, sa.Numeric(9, 6)))


def downgrade() -> None:
    colonnes = _colonnes()
    if LONGITUDE in colonnes:
        op.drop_column(COLLECTIVITES, LONGITUDE)
    if LATITUDE in colonnes:
        op.drop_column(COLLECTIVITES, LATITUDE)
