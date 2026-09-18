"""Ajoute la clé étrangère TB_REF_CENTRES_SANTE.COLLECTIVITE_CODE.

La colonne existe sans contrainte depuis son ajout : à l'époque, des lignes
semées (COL01…) l'auraient violée avant le rechargement des référentiels
CNAM (migration 0025). Ce n'est plus vrai — les 1 510 centres actuels
pointent tous vers une collectivité existante (vérifié le 15/09/2026, 0 ligne
orpheline) — et le modèle ORM déclarait déjà cette relation en commentaire
sans jamais la faire respecter par la base.

ON DELETE SET NULL plutôt que RESTRICT ou CASCADE : supprimer une localité
ne doit ni bloquer sur ses centres, ni les emporter avec elle — seul le
rattachement disparaît.

Revision ID: 20260915_0028
Revises: 20260914_0027
Create Date: 2026-09-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260915_0028"
down_revision = "20260914_0027"
branch_labels = None
depends_on = None

CENTRES = "TB_REF_CENTRES_SANTE"
COLLECTIVITES = "TB_REF_COLLECTIVITES"
CONTRAINTE = "fk_centres_sante_collectivite"


def _contraintes() -> set[str]:
    return {fk["name"] for fk in inspect(op.get_bind()).get_foreign_keys(CENTRES)}


def upgrade() -> None:
    if CONTRAINTE not in _contraintes():
        op.create_foreign_key(
            CONTRAINTE, CENTRES, COLLECTIVITES,
            ["COLLECTIVITE_CODE"], ["COLLECTIVITE_CODE"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if CONTRAINTE in _contraintes():
        op.drop_constraint(CONTRAINTE, CENTRES, type_="foreignkey")
