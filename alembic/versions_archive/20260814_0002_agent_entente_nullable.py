"""Autorise une validation automatique d'entente sans agent conseil."""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260814_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rend l'agent nullable pour la validation réglementaire automatique."""
    op.alter_column(
        "TB_ENTENTES_PREALABLES_STATUTS",
        "AGENT_CODE",
        existing_type=sa.VARCHAR(),
        nullable=True,
    )


def downgrade() -> None:
    """Restaure la contrainte non-nullable."""
    op.alter_column(
        "TB_ENTENTES_PREALABLES_STATUTS",
        "AGENT_CODE",
        existing_type=sa.VARCHAR(),
        nullable=False,
    )