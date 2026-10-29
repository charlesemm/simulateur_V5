"""Référentiels CNAM (collectivités, pharmacies, DCI) et facture brouillée.

- TB_REF_COLLECTIVITES, TB_REF_PHARMACIES, TB_REF_DCI : les trois tables
  qui accueillent la liste publique de la CNAM (seed/donnees). Sur une base
  neuve, la migration 0001 les a déjà créées par create_all() : on ne les
  crée que si elles manquent.
- SEQ_FACTURE_NUMERO : le numéro de facture n'est plus la valeur de la
  séquence mais sa permutation (seed/identifiants.py), définie sur les
  90 000 000 nombres à huit chiffres sans zéro de tête. La séquence doit
  donc s'arrêter là, et non à 99 999 999.

Revision ID: 20260911_0025
Revises: 20260911_0024
Create Date: 2026-09-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260911_0025"
down_revision = "20260911_0024"
branch_labels = None
depends_on = None

COLLECTIVITES = "TB_REF_COLLECTIVITES"
PHARMACIES = "TB_REF_PHARMACIES"
DCI = "TB_REF_DCI"


def _audit() -> list[sa.Column]:
    return [
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
    ]


def upgrade() -> None:
    inspecteur = inspect(op.get_bind())

    if not inspecteur.has_table(COLLECTIVITES):
        op.create_table(
            COLLECTIVITES,
            sa.Column("COLLECTIVITE_CODE", sa.String(30), primary_key=True),
            sa.Column("COLLECTIVITE_DENOMINATION", sa.String(150), nullable=False),
            *_audit(),
        )
    if not inspecteur.has_table(PHARMACIES):
        op.create_table(
            PHARMACIES,
            sa.Column("PHARMACIE_CODE", sa.String(30), primary_key=True),
            sa.Column("PHARMACIE_DENOMINATION", sa.String(255), nullable=False),
            sa.Column("COLLECTIVITE_CODE", sa.String(30), nullable=False),
            *_audit(),
            sa.ForeignKeyConstraint(["COLLECTIVITE_CODE"],
                                    [f"{COLLECTIVITES}.COLLECTIVITE_CODE"]),
        )
    if not inspecteur.has_table(DCI):
        op.create_table(
            DCI,
            sa.Column("DCI_CODE", sa.String(30), primary_key=True),
            sa.Column("DCI_DENOMINATION", sa.String(150), nullable=False),
            *_audit(),
        )

    op.execute('ALTER SEQUENCE "SEQ_FACTURE_NUMERO" MAXVALUE 90000000')


def downgrade() -> None:
    op.execute('ALTER SEQUENCE "SEQ_FACTURE_NUMERO" MAXVALUE 99999999')
    inspecteur = inspect(op.get_bind())
    for table in (PHARMACIES, DCI, COLLECTIVITES):
        if inspecteur.has_table(table):
            op.drop_table(table)
