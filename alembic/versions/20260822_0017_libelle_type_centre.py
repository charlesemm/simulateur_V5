"""Remet le bon libellé dans la colonne du type d'établissement.

Revision ID: 20260822_0017
Revises: 20260822_0016
Create Date: 2026-08-22
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

from seed.constants import HEALTH_CENTER_TYPES

revision = "20260822_0017"
down_revision = "20260822_0016"
branch_labels = None
depends_on = None

TABLE = "TB_FACTURES"


def upgrade() -> None:
    """Recalcule CENTRE_SANTE_TYPE_LIBELLE depuis le code du type.

    Le moteur y rangeait le nom du centre : « Centre de santé de Cocody » au
    lieu de « Centre de santé urbain ». La colonne devenait inutilisable pour
    regrouper par type — exactement ce à quoi elle sert dans un entrepôt.

    Les factures déjà produites sont corrigées ici plutôt que laissées en
    l'état : un jeu de données à moitié juste est pire qu'un jeu faux, parce
    que personne ne sait plus quelle moitié croire.
    """

    connexion = op.get_bind()
    for code, libelle in HEALTH_CENTER_TYPES:
        connexion.execute(
            text(
                f'UPDATE "{TABLE}" SET "CENTRE_SANTE_TYPE_LIBELLE" = :libelle '
                'WHERE "CENTRE_SANTE_TYPE_CODE" = :code '
                'AND ("CENTRE_SANTE_TYPE_LIBELLE" IS DISTINCT FROM :libelle)'
            ),
            {"libelle": libelle, "code": code},
        )


def downgrade() -> None:
    """Ne rétablit rien : l'ancienne valeur était une erreur, pas un état.

    Le nom du centre reste lisible dans TB_REF_CENTRES_SANTE ; le remettre
    ici reviendrait à réintroduire volontairement la confusion.
    """
