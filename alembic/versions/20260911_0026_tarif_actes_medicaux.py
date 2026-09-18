"""Ajoute le tarif de référence des actes médicaux.

Jusqu'ici, chaque prestation valait 10 000 FCFA et chaque acte sous entente
15 000 ou 50 000, quel que soit l'acte : les tarifs existaient dans
seed/constants.py mais n'arrivaient jamais en base. Le moteur facture
désormais autour de ce tarif (de 10 % à 200 %).

Sur une base neuve, la migration 0001 a déjà créé la colonne par
create_all() : on ne l'ajoute que si elle manque.

Revision ID: 20260911_0026
Revises: 20260911_0025
Create Date: 2026-09-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260911_0026"
down_revision = "20260911_0025"
branch_labels = None
depends_on = None

ACTES = "TB_REF_ACTES_MEDICAUX"
TARIF = "ACTE_MEDICAL_TARIF"


def _colonnes() -> set[str]:
    return {colonne["name"] for colonne in inspect(op.get_bind()).get_columns(ACTES)}


def upgrade() -> None:
    if TARIF not in _colonnes():
        op.add_column(ACTES, sa.Column(TARIF, sa.Numeric(15, 2)))


def downgrade() -> None:
    if TARIF in _colonnes():
        op.drop_column(ACTES, TARIF)
