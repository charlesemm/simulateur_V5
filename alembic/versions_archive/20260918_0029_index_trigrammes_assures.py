"""Rend la recherche d'assurés indexable : index trigrammes sur quatre colonnes.

La recherche de l'écran d'accueil (`api/routers/assures.py`) filtre en
`ILIKE '%…%'` sur le nom, les prénoms, le numéro de sécurité sociale et
l'identifiant CMU. Un joker en tête interdit tout index B-tree : chaque
recherche parcourait la table en entier, quatre fois. Un index GIN sur les
trigrammes (`pg_trgm`) est le seul que ce motif sait utiliser.

Les index sont construits en `CONCURRENTLY` : la table reste ouverte aux
écritures pendant la construction, au prix d'une construction hors
transaction. Si elle échoue à mi-chemin, PostgreSQL laisse un index marqué
INVALID que `IF NOT EXISTS` ne reconstruirait pas : le supprimer à la main,
puis relancer la migration.

Revision ID: 20260918_0029
Revises: 20260915_0028
Create Date: 2026-09-18
"""
from __future__ import annotations

from alembic import op

revision = "20260918_0029"
down_revision = "20260915_0028"
branch_labels = None
depends_on = None

TABLE = "TB_REF_ASSURES"
COLONNES = ("ASSURE_NOM", "ASSURE_PRENOMS", "NUMERO_SECU", "ASSURE_NUMERO_IDENTIFIANT")


def _nom_index(colonne: str) -> str:
    return f"ix_ref_assures_trgm_{colonne.lower()}"


def upgrade() -> None:
    # pg_trgm est une extension « de confiance » depuis PostgreSQL 13 : le
    # propriétaire de la base peut l'installer sans être superutilisateur.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        for colonne in COLONNES:
            op.execute(
                f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{_nom_index(colonne)}" '
                f'ON "{TABLE}" USING gin ("{colonne}" gin_trgm_ops)'
            )


def downgrade() -> None:
    """Retire les index. L'extension reste : elle peut servir ailleurs."""

    with op.get_context().autocommit_block():
        for colonne in COLONNES:
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{_nom_index(colonne)}"')
