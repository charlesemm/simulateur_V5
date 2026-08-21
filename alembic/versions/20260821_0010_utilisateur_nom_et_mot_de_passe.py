"""Ajoute le nom d'utilisateur et le changement de mot de passe obligatoire.

Revision ID: 20260821_0010
Revises: 20260821_0009
Create Date: 2026-08-21
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20260821_0010"
down_revision = "20260821_0009"
branch_labels = None
depends_on = None

TABLE = "TB_UTILISATEURS"


def _colonnes() -> set[str]:
    """Retourne les colonnes réellement présentes sur la table."""

    return {colonne["name"] for colonne in inspect(op.get_bind()).get_columns(TABLE)}


def _nom_depuis_email(email: str) -> str:
    """Dérive un nom d'utilisateur lisible de la partie locale d'un e-mail."""

    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower())
    return base or "utilisateur"


def upgrade() -> None:
    """Complète les comptes existants sans exiger d'action de leur part.

    Les comptes déjà créés gardent leur mot de passe : le drapeau reste à faux
    pour eux. Il ne passera à vrai que pour les comptes créés ensuite par un
    administrateur, avec un mot de passe temporaire.
    """

    colonnes = _colonnes()

    if "NOM_UTILISATEUR" not in colonnes:
        op.add_column(TABLE, sa.Column("NOM_UTILISATEUR", sa.String(80), nullable=True))
        op.create_unique_constraint("uq_utilisateurs_nom", TABLE, ["NOM_UTILISATEUR"])

    if "DOIT_CHANGER_MOT_DE_PASSE" not in colonnes:
        op.add_column(
            TABLE,
            sa.Column(
                "DOIT_CHANGER_MOT_DE_PASSE",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    # Chaque compte existant reçoit un nom dérivé de son e-mail. Un suffixe
    # numérique règle les collisions, la colonne étant unique.
    connexion = op.get_bind()
    comptes = connexion.execute(text(
        f'SELECT "UTILISATEUR_UUID", "EMAIL" FROM "{TABLE}" WHERE "NOM_UTILISATEUR" IS NULL'
    )).all()
    attribues: set[str] = {
        ligne[0] for ligne in connexion.execute(text(
            f'SELECT "NOM_UTILISATEUR" FROM "{TABLE}" WHERE "NOM_UTILISATEUR" IS NOT NULL'
        )).all()
    }
    for identifiant, email in comptes:
        nom = _nom_depuis_email(email)
        candidat, suffixe = nom, 2
        while candidat in attribues:
            candidat, suffixe = f"{nom}{suffixe}", suffixe + 1
        attribues.add(candidat)
        connexion.execute(
            text(f'UPDATE "{TABLE}" SET "NOM_UTILISATEUR" = :nom WHERE "UTILISATEUR_UUID" = :id'),
            {"nom": candidat, "id": identifiant},
        )


def downgrade() -> None:
    """Retire les deux colonnes et la contrainte d'unicité associée."""

    colonnes = _colonnes()
    if "DOIT_CHANGER_MOT_DE_PASSE" in colonnes:
        op.drop_column(TABLE, "DOIT_CHANGER_MOT_DE_PASSE")
    if "NOM_UTILISATEUR" in colonnes:
        op.drop_constraint("uq_utilisateurs_nom", TABLE, type_="unique")
        op.drop_column(TABLE, "NOM_UTILISATEUR")
