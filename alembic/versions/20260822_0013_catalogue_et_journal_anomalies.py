"""Ouvre un catalogue d'anomalies et un journal de leurs injections.

Revision ID: 20260822_0013
Revises: 20260821_0012
Create Date: 2026-08-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from anomalies.catalogue import CATALOGUE_INITIAL, DECLENCHEMENT_CONTINU

revision = "20260822_0013"
down_revision = "20260821_0012"
branch_labels = None
depends_on = None

TABLE_CATALOGUE = "TB_REF_ANOMALIES"
TABLE_JOURNAL = "TB_ANOMALIES_INJECTIONS"

AUDIT = (
    sa.Column("DATE_CREATION", sa.DateTime(timezone=True),
              server_default=sa.func.now(), nullable=False),
    sa.Column("UTILISATEUR_ID_CREATION", sa.String(100)),
    sa.Column("DATE_MODIFICATION", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100)),
)


def upgrade() -> None:
    """Crée les deux tables, puis reporte le réglage global sur chaque type.

    Le taux global valait jusqu'ici pour les cinq types à la fois : chacun le
    reçoit donc en propre, afin que rien ne change tant que personne ne les
    règle séparément.
    """

    inspecteur = inspect(op.get_bind())

    if not inspecteur.has_table(TABLE_CATALOGUE):
        op.create_table(
            TABLE_CATALOGUE,
            sa.Column("ANOMALIE_CODE", sa.String(40), primary_key=True),
            sa.Column("ANOMALIE_LIBELLE", sa.String(150), nullable=False),
            sa.Column("ANOMALIE_TABLE_CIBLE", sa.String(80), nullable=False),
            sa.Column("ANOMALIE_COLONNE_CIBLE", sa.String(80), nullable=False),
            sa.Column("ANOMALIE_SEVERITE", sa.String(20), nullable=False),
            sa.Column("ANOMALIE_ACTIVE", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("ANOMALIE_TAUX", sa.Numeric(3, 2), nullable=False, server_default=sa.text("0.00")),
            *AUDIT,
        )

    if not inspecteur.has_table(TABLE_JOURNAL):
        op.create_table(
            TABLE_JOURNAL,
            sa.Column("INJECTION_ID", PostgreSQLUUID(as_uuid=True), primary_key=True),
            sa.Column("ANOMALIE_CODE", sa.String(40), nullable=False),
            sa.Column("SIMULATION_ID", PostgreSQLUUID(as_uuid=True)),
            sa.Column("PASSAGE_ID", sa.String(64)),
            sa.Column("CIBLE_CLE", sa.String(100)),
            sa.Column("VALEUR_ORIGINE", sa.Text),
            sa.Column("VALEUR_INJECTEE", sa.Text),
            *AUDIT,
            sa.ForeignKeyConstraint(
                ["ANOMALIE_CODE"], [f"{TABLE_CATALOGUE}.ANOMALIE_CODE"],
                name="fk_anomalies_injections_type",
            ),
            sa.ForeignKeyConstraint(
                ["SIMULATION_ID"], ["TB_SIMULATIONS.SIMULATION_ID"],
                name="fk_anomalies_injections_simulation",
            ),
        )
        op.create_index("IX_ANOMALIES_INJECTIONS_SIMULATION", TABLE_JOURNAL, ["SIMULATION_ID"])
        op.create_index("IX_ANOMALIES_INJECTIONS_CODE", TABLE_JOURNAL, ["ANOMALIE_CODE"])

    connexion = op.get_bind()

    # Le taux global sert d'amorce ; à défaut de ligne de réglage, personne
    # n'avait encore rien demandé, et zéro est la bonne valeur.
    taux_global = connexion.execute(text(
        'SELECT "RATE" FROM "TB_CONFIG_ANOMALIES" ORDER BY "CONFIG_ID" LIMIT 1'
    )).scalar()
    taux_global = 0 if taux_global is None else taux_global

    # La table peut déjà porter les colonnes que la migration 0014 ajoutera :
    # sur une base neuve, la migration 0001 crée le schéma tel que les modèles
    # le décrivent AUJOURD'HUI, famille comprise et non nulle. L'insertion doit
    # donc s'adapter aux colonnes réellement présentes, faute de quoi elle
    # échoue sur toute base créée de zéro — et seulement sur celles-là.
    # Inspecteur relu : la table vient peut-être d'être créée juste au-dessus,
    # et celui du début de la fonction ne la connaîtrait pas.
    colonnes_presentes = {
        colonne["name"]
        for colonne in inspect(op.get_bind()).get_columns(TABLE_CATALOGUE)
    }
    # Les trois colonnes que 0014 ajoutera plus tard, toutes non nulles. Le
    # declenchement n'est pas porte par le catalogue : il vaut « continu » a
    # l'origine, ce que 0014 pose aussi comme defaut.
    colonnes_tardives = {
        "ANOMALIE_FAMILLE": lambda type_anomalie: type_anomalie.famille,
        "ANOMALIE_COULEUR": lambda type_anomalie: type_anomalie.couleur,
        "ANOMALIE_DECLENCHEMENT": lambda _: DECLENCHEMENT_CONTINU,
    }
    supplements = [nom for nom in colonnes_tardives if nom in colonnes_presentes]

    noms = [
        "ANOMALIE_CODE", "ANOMALIE_LIBELLE", "ANOMALIE_TABLE_CIBLE",
        "ANOMALIE_COLONNE_CIBLE", "ANOMALIE_SEVERITE", "ANOMALIE_ACTIVE",
        "ANOMALIE_TAUX", "UTILISATEUR_ID_CREATION", *supplements,
    ]
    valeurs = [
        ":code", ":libelle", ":table_cible", ":colonne_cible", ":severite",
        "true", ":taux", "'migration'",
        *(f":{nom.lower()}" for nom in supplements),
    ]
    colonnes_sql = ", ".join('"{}"'.format(nom) for nom in noms)
    requete = text(
        f'INSERT INTO "{TABLE_CATALOGUE}" ({colonnes_sql}) '
        f'VALUES ({", ".join(valeurs)}) '
        'ON CONFLICT ("ANOMALIE_CODE") DO NOTHING'
    )

    for type_anomalie in CATALOGUE_INITIAL:
        parametres = {
            "code": type_anomalie.code,
            "libelle": type_anomalie.libelle,
            "table_cible": type_anomalie.table_cible,
            "colonne_cible": type_anomalie.colonne_cible,
            "severite": type_anomalie.severite,
            "taux": taux_global,
        }
        for nom in supplements:
            parametres[nom.lower()] = colonnes_tardives[nom](type_anomalie)
        connexion.execute(requete, parametres)


def downgrade() -> None:
    """Retire le journal puis le catalogue, dans cet ordre à cause de la clé."""

    inspecteur = inspect(op.get_bind())
    if inspecteur.has_table(TABLE_JOURNAL):
        op.drop_table(TABLE_JOURNAL)
    if inspecteur.has_table(TABLE_CATALOGUE):
        op.drop_table(TABLE_CATALOGUE)
