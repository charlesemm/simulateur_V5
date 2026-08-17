"""Ajoute le journal technique horodaté en temps simulé."""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0003"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crée le journal et ses index de recherche temporelle."""

    op.create_table(
        "TB_EVENEMENTS_METIER",
        sa.Column("EVENEMENT_ID", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("TYPE_EVENEMENT", sa.String(80), nullable=False),
        sa.Column("PASSAGE_ID", sa.String(64), nullable=False),
        sa.Column("SIMULATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("PAYLOAD", postgresql.JSONB, nullable=False),
        sa.Column("DATE_CREATION", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100), nullable=True),
        sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True), nullable=True),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100), nullable=True),
    )
    op.create_index("IX_EVENEMENTS_SIMULATED_AT", "TB_EVENEMENTS_METIER", ["SIMULATED_AT"])
    op.create_index("IX_EVENEMENTS_TYPE", "TB_EVENEMENTS_METIER", ["TYPE_EVENEMENT"])
    op.create_index("IX_EVENEMENTS_PASSAGE", "TB_EVENEMENTS_METIER", ["PASSAGE_ID"])


def downgrade() -> None:
    """Supprime uniquement le journal technique de l'étape 4."""

    op.drop_table("TB_EVENEMENTS_METIER")