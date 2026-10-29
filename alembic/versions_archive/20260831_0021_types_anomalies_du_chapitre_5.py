"""Inscrit au catalogue les six types du chapitre 5 du cahier Qualité.

Ils comblent les trois dimensions que rien ne savait éprouver : Unicité,
Complétude et Conformité technique.

Revision ID: 20260831_0021
Revises: 20260828_0020
Create Date: 2026-08-31
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

from anomalies.catalogue import (
    CATALOGUE_INITIAL, CHAMP_OBLIGATOIRE_VIDE, DECLENCHEMENT_CONTINU,
    DOUBLON_APPROCHANT, DOUBLON_EXACT, ENCODAGE_CASSE, FORMAT_DATE_INCOHERENT,
    TENTATIVE_INJECTION,
)

revision = "20260831_0021"
down_revision = "20260828_0020"
branch_labels = None
depends_on = None

TABLE = "TB_REF_ANOMALIES"

# Les six codes que cette migration apporte. Écrits en dur plutôt que déduits
# du catalogue : une migration doit décrire ce qu'elle a fait le jour où elle
# a été écrite, et non ce que le code contiendra plus tard. Sans cela, sa
# marche arrière emporterait les types ajoutés par les migrations suivantes.
CODES_AJOUTES = (
    DOUBLON_EXACT,
    DOUBLON_APPROCHANT,
    CHAMP_OBLIGATOIRE_VIDE,
    ENCODAGE_CASSE,
    FORMAT_DATE_INCOHERENT,
    TENTATIVE_INJECTION,
)


def upgrade() -> None:
    """Ajoute les six types, sans toucher aux réglages déjà en place.

    Le ON CONFLICT protège les taux et les moments qu'un opérateur aurait
    réglés : une migration ne doit pas défaire ce qu'un humain a décidé.

    Ils arrivent à taux nul : présents au catalogue, silencieux tant que
    personne ne les demande.
    """

    par_code = {
        type_anomalie.code: type_anomalie for type_anomalie in CATALOGUE_INITIAL
    }
    connexion = op.get_bind()
    for code in CODES_AJOUTES:
        type_anomalie = par_code[code]
        connexion.execute(
            text(
                f'INSERT INTO "{TABLE}" '
                '("ANOMALIE_CODE", "ANOMALIE_LIBELLE", "ANOMALIE_FAMILLE", '
                '"ANOMALIE_COULEUR", "ANOMALIE_TABLE_CIBLE", '
                '"ANOMALIE_COLONNE_CIBLE", "ANOMALIE_SEVERITE", '
                '"ANOMALIE_ACTIVE", "ANOMALIE_TAUX", "ANOMALIE_DECLENCHEMENT", '
                '"UTILISATEUR_ID_CREATION") '
                "VALUES (:code, :libelle, :famille, :couleur, :table_cible, "
                ":colonne_cible, :severite, true, 0.00, :declenchement, 'migration') "
                'ON CONFLICT ("ANOMALIE_CODE") DO NOTHING'
            ),
            {
                "code": type_anomalie.code,
                "libelle": type_anomalie.libelle,
                "famille": type_anomalie.famille,
                "couleur": type_anomalie.couleur,
                "table_cible": type_anomalie.table_cible,
                "colonne_cible": type_anomalie.colonne_cible,
                "severite": type_anomalie.severite,
                "declenchement": DECLENCHEMENT_CONTINU,
            },
        )


def downgrade() -> None:
    """Retire les six types, et le journal qui s'y rapporte.

    Le journal part d'abord : ses lignes désignent le catalogue par clé
    étrangère. Le corrigé des campagnes, lui, n'a pas de contrainte vers le
    catalogue — il garde le code en texte — et n'est donc pas touché : effacer
    le corrigé d'une campagne déjà passée reviendrait à détruire la preuve de
    ce qui a été injecté.
    """

    codes = list(CODES_AJOUTES)
    connexion = op.get_bind()
    connexion.execute(
        text('DELETE FROM "TB_ANOMALIES_INJECTIONS" WHERE "ANOMALIE_CODE" = ANY(:codes)'),
        {"codes": codes},
    )
    connexion.execute(
        text(f'DELETE FROM "{TABLE}" WHERE "ANOMALIE_CODE" = ANY(:codes)'),
        {"codes": codes},
    )
