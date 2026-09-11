"""Ajoute la séquence qui numérote les factures sur huit chiffres.

FACTURE_NUMERO reste la clé primaire de TB_FACTURES, sans remise à zéro par
exécution. Un dérivé aléatoire de passage_id (comme pour le dossier ou
l'entente) ne convient pas ici : sur seulement huit chiffres (10^8 valeurs),
le paradoxe des anniversaires rend la collision probable bien avant que
l'espace soit épuisé, alors que l'outil est justement fait pour accumuler
toutes les lignes de toutes les exécutions. Une séquence Postgres garantit
l'unicité même sous plusieurs passages concurrents.

Revision ID: 20260911_0023
Revises: 20260907_0022
Create Date: 2026-09-11
"""
from __future__ import annotations

from alembic import op

revision = "20260911_0023"
down_revision = "20260907_0022"
branch_labels = None
depends_on = None

SEQUENCE = "SEQ_FACTURE_NUMERO"


def upgrade() -> None:
    """Crée la séquence, sans CYCLE.

    Mieux vaut un arrêt net à 99 999 999 factures qu'une collision
    silencieuse sur une clé primaire déjà utilisée.
    """
    op.execute(
        f'CREATE SEQUENCE "{SEQUENCE}" AS BIGINT '
        f"MINVALUE 1 MAXVALUE 99999999 START WITH 1 NO CYCLE"
    )


def downgrade() -> None:
    op.execute(f'DROP SEQUENCE "{SEQUENCE}"')
