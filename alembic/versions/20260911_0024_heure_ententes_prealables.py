"""Ajoute l'heure aux dates de l'entente préalable, pose la date de fin.

ENTENTE_PREALABLE_DATE_DEBUT/FIN (TB_ENTENTES_PREALABLES) et
STATUT_DATE_DEBUT/FIN (TB_ENTENTES_PREALABLES_STATUTS) passent de Date à
Timestamp avec fuseau : le moteur posait jusqu'ici une date nue, perdant
l'heure de la décision, et ne renseignait jamais DATE_FIN. La conversion
Date -> Timestamp est directe (minuit UTC pour les lignes existantes) ;
aucune ligne existante ne récupère rétroactivement une date de fin qu'elle
n'a jamais eue.

Revision ID: 20260911_0024
Revises: 20260911_0023
Create Date: 2026-09-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260911_0024"
down_revision = "20260911_0023"
branch_labels = None
depends_on = None

ENTENTES = "TB_ENTENTES_PREALABLES"
STATUTS = "TB_ENTENTES_PREALABLES_STATUTS"


def upgrade() -> None:
    op.alter_column(
        ENTENTES, "ENTENTE_PREALABLE_DATE_DEBUT",
        type_=sa.DateTime(timezone=True), nullable=False,
        postgresql_using='"ENTENTE_PREALABLE_DATE_DEBUT"::timestamptz',
    )
    op.alter_column(
        ENTENTES, "ENTENTE_PREALABLE_DATE_FIN",
        type_=sa.DateTime(timezone=True),
        postgresql_using='"ENTENTE_PREALABLE_DATE_FIN"::timestamptz',
    )
    # STATUT_DATE_DEBUT fait partie de la clé primaire composite : Postgres
    # autorise l'ALTER COLUMN TYPE sur une colonne de PK tant que l'index
    # sous-jacent reste valide, ce qu'une conversion date -> timestamptz
    # (élargissement, jamais de perte) garantit.
    op.alter_column(
        STATUTS, "STATUT_DATE_DEBUT",
        type_=sa.DateTime(timezone=True), nullable=False,
        postgresql_using='"STATUT_DATE_DEBUT"::timestamptz',
    )
    op.alter_column(
        STATUTS, "STATUT_DATE_FIN",
        type_=sa.DateTime(timezone=True),
        postgresql_using='"STATUT_DATE_FIN"::timestamptz',
    )


def downgrade() -> None:
    op.alter_column(
        STATUTS, "STATUT_DATE_FIN",
        type_=sa.Date(), postgresql_using='"STATUT_DATE_FIN"::date',
    )
    op.alter_column(
        STATUTS, "STATUT_DATE_DEBUT",
        type_=sa.Date(), nullable=False,
        postgresql_using='"STATUT_DATE_DEBUT"::date',
    )
    op.alter_column(
        ENTENTES, "ENTENTE_PREALABLE_DATE_FIN",
        type_=sa.Date(), postgresql_using='"ENTENTE_PREALABLE_DATE_FIN"::date',
    )
    op.alter_column(
        ENTENTES, "ENTENTE_PREALABLE_DATE_DEBUT",
        type_=sa.Date(), nullable=False,
        postgresql_using='"ENTENTE_PREALABLE_DATE_DEBUT"::date',
    )
