"""Ajoute l'identité complète de l'assuré et libère le numéro de dossier.

Revision ID: 20260814_0006
Revises: 20260814_0005
Create Date: 2026-08-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260814_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    """Retourne les colonnes réellement présentes sur la table."""

    return {colonne["name"] for colonne in inspect(op.get_bind()).get_columns(table)}


def _contraintes_check(table: str) -> set[str]:
    """Retourne les contraintes CHECK réellement présentes sur la table."""

    return {
        contrainte["name"]
        for contrainte in inspect(op.get_bind()).get_check_constraints(table)
    }


def upgrade() -> None:
    """Complète l'assuré des champs exigés par les bons de prise en charge.

    La révision 20260814_0001 appelle Base.metadata.create_all() : sur une base
    neuve elle crée déjà les colonnes ci-dessous, telles que le modèle les
    déclare aujourd'hui. Chaque ajout est donc conditionné à l'absence réelle
    de la colonne, pour rester applicable sur une base neuve comme sur une base
    créée avant l'évolution du modèle.
    """

    colonnes = _colonnes("TB_REF_ASSURES")

    # Les quatre feuilles de soins réclament « NOM ET PRENOM(S) » et
    # « NE(E) LE » : ni l'un ni l'autre n'existait sur l'assuré.
    if "ASSURE_PRENOMS" not in colonnes:
        op.add_column(
            "TB_REF_ASSURES",
            sa.Column("ASSURE_PRENOMS", sa.String(150), nullable=True),
        )
    if "ASSURE_DATE_NAISSANCE" not in colonnes:
        op.add_column(
            "TB_REF_ASSURES",
            sa.Column("ASSURE_DATE_NAISSANCE", sa.Date(), nullable=True),
        )

    # Le régime appartient à la personne et fixe le taux de remboursement
    # de toutes ses factures.
    if "REGIME_CODE" not in colonnes:
        op.add_column(
            "TB_REF_ASSURES",
            sa.Column("REGIME_CODE", sa.String(10), nullable=True),
        )

    # La contrainte n'est déclarée dans aucun modèle : elle reste à créer.
    if "ck_assures_regime_valide" not in _contraintes_check("TB_REF_ASSURES"):
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

    if "ck_assures_regime_valide" in _contraintes_check("TB_REF_ASSURES"):
        op.drop_constraint("ck_assures_regime_valide", "TB_REF_ASSURES", type_="check")

    colonnes = _colonnes("TB_REF_ASSURES")
    for nom in ("REGIME_CODE", "ASSURE_DATE_NAISSANCE", "ASSURE_PRENOMS"):
        if nom in colonnes:
            op.drop_column("TB_REF_ASSURES", nom)