"""Inscrit au catalogue les types d'anomalies ajoutés pour les six familles.

Revision ID: 20260822_0018
Revises: 20260822_0017
Create Date: 2026-08-22
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

from anomalies.catalogue import CATALOGUE_INITIAL, DECLENCHEMENT_CONTINU

revision = "20260822_0018"
down_revision = "20260822_0017"
branch_labels = None
depends_on = None

TABLE = "TB_REF_ANOMALIES"


def upgrade() -> None:
    """Ajoute les types absents, sans toucher aux réglages déjà en place.

    Le ON CONFLICT protège les taux et les moments qu'un opérateur aurait
    réglés : une migration ne doit pas défaire ce qu'un humain a décidé.

    Les nouveaux types arrivent à taux nul et actifs : présents au catalogue,
    visibles dans la console, mais silencieux tant que personne ne les demande.
    """

    connexion = op.get_bind()
    for type_anomalie in CATALOGUE_INITIAL:
        connexion.execute(
            text(
                f'INSERT INTO "{TABLE}" '
                '("ANOMALIE_CODE", "ANOMALIE_LIBELLE", "ANOMALIE_FAMILLE", '
                '"ANOMALIE_COULEUR", "ANOMALIE_TABLE_CIBLE", '
                '"ANOMALIE_COLONNE_CIBLE", "ANOMALIE_SEVERITE", '
                '"ANOMALIE_ACTIVE", "ANOMALIE_TAUX", "ANOMALIE_DECLENCHEMENT", '
                '"UTILISATEUR_ID_CREATION") '
                "VALUES (:code, :libelle, :famille, :couleur, :table_cible, "
                ":colonne_cible, :severite, true, 0.00, :declenchement, 'migration') "
                'ON CONFLICT ("ANOMALIE_CODE") DO NOTHING'
            ),
            {
                "code": type_anomalie.code,
                "libelle": type_anomalie.libelle,
                "famille": type_anomalie.famille,
                "couleur": type_anomalie.couleur,
                "table_cible": type_anomalie.table_cible,
                "colonne_cible": type_anomalie.colonne_cible,
                "severite": type_anomalie.severite,
                "declenchement": DECLENCHEMENT_CONTINU,
            },
        )


def downgrade() -> None:
    """Retire les types ajoutés, et le journal qui s'y rapporte.

    Le journal doit partir d'abord : ses lignes désignent le catalogue par
    clé étrangère.
    """

    codes = tuple(
        type_anomalie.code for type_anomalie in CATALOGUE_INITIAL
        if type_anomalie.code not in (
            "MONTANT_ABERRANT", "DATE_ANTIDATEE", "QUANTITE_EXCESSIVE",
            "NUMERO_SECU_INVALIDE", "EMAIL_INVALIDE",
        )
    )
    if not codes:
        return

    connexion = op.get_bind()
    connexion.execute(
        text('DELETE FROM "TB_ANOMALIES_INJECTIONS" WHERE "ANOMALIE_CODE" = ANY(:codes)'),
        {"codes": list(codes)},
    )
    connexion.execute(
        text(f'DELETE FROM "{TABLE}" WHERE "ANOMALIE_CODE" = ANY(:codes)'),
        {"codes": list(codes)},
    )
