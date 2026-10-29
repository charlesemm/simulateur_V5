"""N'autorise que les régimes réels sur la facture et l'assuré.

Revision ID: 20260821_0009
Revises: 20260821_0008
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260821_0009"
down_revision = "20260821_0008"
branch_labels = None
depends_on = None

NOM = "ck_factures_regime_valide"

# TB_TV_REGIMES ne contient que RAM et RGB. « CMU » désigne le dispositif
# dans son ensemble, pas un régime : le moteur l'écrivait pourtant en dur sur
# chaque facture avant que le régime ne soit lu depuis l'assuré. Cette
# contrainte interdit désormais la confusion au niveau de la base.
CONDITION = "\"REGIME_CODE\" IS NULL OR \"REGIME_CODE\" IN ('RAM', 'RGB')"


def _existe(nom: str) -> bool:
    """Indique si une contrainte de ce nom est déjà posée sur la base."""

    resultat = op.get_bind().execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :nom"), {"nom": nom}
    )
    return resultat.scalar() is not None


def upgrade() -> None:
    """Pose la contrainte de validité du régime sur la facture.

    Échoue s'il subsiste des factures portant un autre code : il faut alors
    les corriger ou les supprimer avant de rejouer la migration.
    """

    if not _existe(NOM):
        op.create_check_constraint(NOM, "TB_FACTURES", CONDITION)


def downgrade() -> None:
    """Retire la contrainte, sans toucher aux données."""

    if _existe(NOM):
        op.drop_constraint(NOM, "TB_FACTURES", type_="check")
