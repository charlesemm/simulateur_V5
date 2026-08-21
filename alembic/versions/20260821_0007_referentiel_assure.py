"""Ajoute les neuf tables du référentiel assuré étendu.

Revision ID: 20260821_0007
Revises: 20260814_0006
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

from app.models import Base

revision = "20260821_0007"
down_revision = "20260814_0006"
branch_labels = None
depends_on = None

TABLES = (
    "TB_TV_REGIMES",
    "TB_TV_LOCALISATION_PAYS",
    "TB_TV_LOCALISATION_REGIONS",
    "TB_TV_LOCALISATION_DEPARTEMENTS",
    "TB_TV_LOCALISATION_LOCALITES",
    "TB_ASSURES_IDENTIFIANTS",
    "TB_ASSURES_PROFESSIONS",
    "TB_ASSURES_INFOS_NAISSANCE",
    "TB_ASSURES_DROITS",
)

# Chaque entrée interdit à un même assuré de porter deux lignes qui se
# recouvrent dans le temps pour la même clé métier. Sans cela, une lecture
# « à la date des soins » pourrait ramener deux résultats contradictoires.
EXCLUSIONS = (
    (
        "TB_ASSURES_IDENTIFIANTS",
        "ex_identifiants_periodes",
        '"PERSONNE_UUID" WITH =, "TYPE_IDENTIFIANT_CODE" WITH =, '
        'tstzrange("IDENTIFIANT_DATE_DEBUT", "IDENTIFIANT_DATE_FIN") WITH &&',
    ),
    (
        "TB_ASSURES_PROFESSIONS",
        "ex_professions_periodes",
        '"PERSONNE_UUID" WITH =, "PROFESSION_CODE" WITH =, '
        'tstzrange("PROFESSION_DATE_DEBUT", "PROFESSION_DATE_FIN") WITH &&',
    ),
    (
        "TB_ASSURES_INFOS_NAISSANCE",
        "ex_naissance_periodes",
        '"PERSONNE_UUID" WITH =, '
        'tstzrange("NAISSANCE_DATE_DEBUT", "NAISSANCE_DATE_FIN") WITH &&',
    ),
)


def _contrainte_existe(nom: str) -> bool:
    """Indique si une contrainte de ce nom est déjà posée sur la base."""

    resultat = op.get_bind().execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :nom"), {"nom": nom}
    )
    return resultat.scalar() is not None


def upgrade() -> None:
    """Crée les tables absentes, puis verrouille les périodes historisées."""

    bind = op.get_bind()

    # create_all avec checkfirst laisse intactes les tables déjà créées par la
    # révision 0001 sur une base neuve, et crée les manquantes sur une base
    # existante. Le chantier « migration figée » remplacera cela par du SQL
    # explicite.
    Base.metadata.create_all(
        bind,
        tables=[Base.metadata.tables[nom] for nom in TABLES],
        checkfirst=True,
    )

    # gist ne sait comparer l'égalité d'un uuid ou d'un varchar qu'avec cette
    # extension ; sans elle, les contraintes ci-dessous sont refusées.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    for table, nom, definition in EXCLUSIONS:
        if not _contrainte_existe(nom):
            op.execute(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{nom}" '
                f"EXCLUDE USING gist ({definition})"
            )


def downgrade() -> None:
    """Retire les neuf tables et leurs contraintes.

    L'extension btree_gist est laissée en place : elle peut servir ailleurs
    et sa suppression échouerait si un autre objet en dépend.
    """

    for table, nom, _ in EXCLUSIONS:
        if _contrainte_existe(nom):
            op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{nom}"')

    inspecteur = inspect(op.get_bind())
    existantes = set(inspecteur.get_table_names())
    for nom in reversed(TABLES):
        if nom in existantes:
            op.drop_table(nom)
