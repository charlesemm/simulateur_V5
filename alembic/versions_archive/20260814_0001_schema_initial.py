"""Crée le schéma initial complet du simulateur CMU.

Révision : 20260814_0001
Révision précédente : aucune
"""

from collections.abc import Sequence

from alembic import op

from app.models import Base


revision: str = "20260814_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crée les vingt-deux tables, leurs contraintes et leurs index uniques."""

    # AuditMixin injecte les quatre colonnes d'audit sans duplication.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Supprime les tables dans l'ordre inverse de leurs dépendances."""

    # SQLAlchemy traite la contrainte différée du cycle facture-entente.
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=False)