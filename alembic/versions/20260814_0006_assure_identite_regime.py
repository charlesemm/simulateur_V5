"""Ajoute l'identité complète de l'assuré et libère le numéro de dossier.

Revision ID: 20260814_0006
Revises: 20260814_0005
Create Date: 2026-08-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Complète l'assuré des champs exigés par les bons de prise en charge."""

    # Les quatre feuilles de soins réclament « NOM ET PRENOM(S) » et
    # « NE(E) LE » : ni l'un ni l'autre n'existait sur l'assuré.
    op.add_column(
        "TB_REF_ASSURES",
        sa.Column("ASSURE_PRENOMS", sa.String(150), nullable=True),
    )
    op.add_column(
        "TB_REF_ASSURES",
        sa.Column("ASSURE_DATE_NAISSANCE", sa.Date(), nullable=True),
    )

    # Le régime appartient à la personne et fixe le taux de remboursement
    # de toutes ses factures.
    op.add_column(
        "TB_REF_ASSURES",
        sa.Column("REGIME_CODE", sa.String(10), nullable=True),
    )
    op.create_check_constraint(
        "ck_assures_regime_valide",
        "TB_REF_ASSURES",
        "\"REGIME_CODE\" IS NULL OR \"REGIME_CODE\" IN ('RAM', 'RGB')",
    )

    # Le simulateur ne produit plus de numéro de dossier.
    op.alter_column(
        "TB_FACTURES", "DOSSIER_NUMERO",
        existing_type=sa.VARCHAR(50), nullable=True,
    )
    op.alter_column(
        "TB_ENTENTES_PREALABLES", "DOSSIER_NUMERO",
        existing_type=sa.VARCHAR(50), nullable=True,
    )


def downgrade() -> None:
    """Restaure les contraintes précédentes.

    Le retour arrière échoue si des factures ou des ententes ont déjà été
    créées sans numéro de dossier ; il faut alors les supprimer d'abord.
    """

    op.alter_column(
        "TB_ENTENTES_PREALABLES", "DOSSIER_NUMERO",
        existing_type=sa.VARCHAR(50), nullable=False,
    )
    op.alter_column(
        "TB_FACTURES", "DOSSIER_NUMERO",
        existing_type=sa.VARCHAR(50), nullable=False,
    )
    op.drop_constraint("ck_assures_regime_valide", "TB_REF_ASSURES", type_="check")
    op.drop_column("TB_REF_ASSURES", "REGIME_CODE")
    op.drop_column("TB_REF_ASSURES", "ASSURE_DATE_NAISSANCE")
    op.drop_column("TB_REF_ASSURES", "ASSURE_PRENOMS")
