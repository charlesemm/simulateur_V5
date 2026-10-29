"""Interdit à un assuré de porter deux professions sur la même période.

Revision ID: 20260821_0008
Revises: 20260821_0007
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260821_0008"
down_revision = "20260821_0007"
branch_labels = None
depends_on = None

NOM = "ex_professions_periodes"

# La révision 0007 excluait les chevauchements par couple (assuré, profession) :
# deux professions différentes pouvaient donc se recouvrir. Le régime de
# l'assuré se déduisant de sa profession, cela rendait le régime ambigu -- et
# un simple ré-ensemencement suffisait à créer le cas, la profession faisant
# partie de la clé primaire.
ANCIENNE = (
    '"PERSONNE_UUID" WITH =, "PROFESSION_CODE" WITH =, '
    'tstzrange("PROFESSION_DATE_DEBUT", "PROFESSION_DATE_FIN") WITH &&'
)
NOUVELLE = (
    '"PERSONNE_UUID" WITH =, '
    'tstzrange("PROFESSION_DATE_DEBUT", "PROFESSION_DATE_FIN") WITH &&'
)


def _existe() -> bool:
    """Indique si la contrainte est déjà posée sur la base."""

    resultat = op.get_bind().execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :nom"), {"nom": NOM}
    )
    return resultat.scalar() is not None


def _remplacer(definition: str) -> None:
    """Repose la contrainte avec la définition demandée."""

    if _existe():
        op.execute(f'ALTER TABLE "TB_ASSURES_PROFESSIONS" DROP CONSTRAINT "{NOM}"')
    op.execute(
        f'ALTER TABLE "TB_ASSURES_PROFESSIONS" ADD CONSTRAINT "{NOM}" '
        f"EXCLUDE USING gist ({definition})"
    )


def upgrade() -> None:
    """Resserre la contrainte sur le seul couple (assuré, période).

    Échoue si des professions qui se chevauchent subsistent : il faut alors
    les purger avant de rejouer la migration.
    """

    _remplacer(NOUVELLE)


def downgrade() -> None:
    """Rétablit la portée d'origine, par couple (assuré, profession)."""

    _remplacer(ANCIENNE)
