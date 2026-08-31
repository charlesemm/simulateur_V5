"""Modèle SQLAlchemy de la table des campagnes de test.

Comme `simulation/models.py` et `anomalies/models.py`, ce modèle n'est pas
exporté par `app/models/__init__.py` : la migration 0001 appelle
`Base.metadata.create_all()` et créerait sinon la table en double avec la
migration qui l'introduit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

# Le cycle d'une campagne, du cahier des charges : on la crée, on génère son
# jeu piégé, on le transmet, on reçoit le rapport de l'outil testé, on le note.
STATUT_CREEE = "creee"
STATUT_GENERATION = "generation"
STATUT_GENEREE = "generee"
STATUT_TRANSMISE = "transmise"
STATUT_RAPPORT_RECU = "rapport_recu"
STATUT_NOTEE = "notee"
# Un échange raté n'est pas un mauvais score : il a son propre statut, pour ne
# jamais être lu comme « l'outil n'a rien détecté » (exigence 2.5).
STATUT_ECHEC_ECHANGE = "echec_echange"

STATUTS = (
    STATUT_CREEE,
    STATUT_GENERATION,
    STATUT_GENEREE,
    STATUT_TRANSMISE,
    STATUT_RAPPORT_RECU,
    STATUT_NOTEE,
    STATUT_ECHEC_ECHANGE,
)

LIBELLES_STATUTS: dict[str, str] = {
    STATUT_CREEE: "Créée",
    STATUT_GENERATION: "Génération en cours",
    STATUT_GENEREE: "Jeu généré",
    STATUT_TRANSMISE: "Transmise à l'outil",
    STATUT_RAPPORT_RECU: "Rapport reçu",
    STATUT_NOTEE: "Notée",
    STATUT_ECHEC_ECHANGE: "Échec d'échange",
}


class Campagne(AuditMixin, Base):
    """Une campagne de test, de sa création à sa note.

    Elle porte sa graine dès la création : c'est elle qui rend le jeu de
    données rejouable à l'identique, et une graine tirée au moment de la
    génération ne serait pas visible avant qu'il soit trop tard pour la noter.
    """

    __tablename__ = "TB_CAMPAGNES"
    __table_args__ = (
        Index("IX_CAMPAGNES_DATE_CREATION", "DATE_CREATION"),
        Index("IX_CAMPAGNES_STATUT", "CAMPAGNE_STATUT"),
    )

    campagne_id: Mapped[uuid.UUID] = mapped_column(
        "CAMPAGNE_ID", PostgreSQLUUID(as_uuid=True), primary_key=True,
        default=uuid.uuid4,
    )
    # Référence lisible à l'œil, du type C-2026-018 : c'est elle qu'on cite
    # dans un compte rendu, pas un UUID de trente-six caractères.
    campagne_reference: Mapped[str] = mapped_column(
        "CAMPAGNE_REFERENCE", String(20), nullable=False, unique=True
    )
    campagne_libelle: Mapped[str] = mapped_column(
        "CAMPAGNE_LIBELLE", String(150), nullable=False
    )
    campagne_statut: Mapped[str] = mapped_column(
        "CAMPAGNE_STATUT", String(30), nullable=False, default=STATUT_CREEE
    )
    # La graine tient dans un entier 32 bits signé, mais la colonne est large :
    # une graine est une valeur, pas un compteur, et rien n'oblige à la borner
    # côté base si un jour elle vient d'ailleurs.
    campagne_graine: Mapped[int] = mapped_column(
        "CAMPAGNE_GRAINE", BigInteger, nullable=False
    )
    campagne_palier: Mapped[str] = mapped_column(
        "CAMPAGNE_PALIER", String(20), nullable=False
    )
    campagne_volume_cible: Mapped[int] = mapped_column(
        "CAMPAGNE_VOLUME_CIBLE", Integer, nullable=False
    )
    # Réglage des anomalies, périmètre des dimensions, adresse de l'outil
    # testé : tout ce que les modules suivants ajouteront sans migration.
    campagne_parametres: Mapped[dict[str, Any]] = mapped_column(
        "CAMPAGNE_PARAMETRES", JSONB, nullable=False, default=dict
    )
    campagne_date_fin: Mapped[datetime | None] = mapped_column(
        "CAMPAGNE_DATE_FIN", DateTime(timezone=True)
    )
    # Ce que la génération a produit. Nul tant qu'elle n'a pas eu lieu.
    campagne_date_generation: Mapped[datetime | None] = mapped_column(
        "CAMPAGNE_DATE_GENERATION", DateTime(timezone=True)
    )
    campagne_lignes_generees: Mapped[int] = mapped_column(
        "CAMPAGNE_LIGNES_GENEREES", Integer, nullable=False, default=0
    )
    campagne_anomalies_posees: Mapped[int] = mapped_column(
        "CAMPAGNE_ANOMALIES_POSEES", Integer, nullable=False, default=0
    )
    # Empreinte SHA-256 du fichier produit. C'est elle qui prouve, à l'œil et
    # sans ouvrir les fichiers, que deux campagnes de même graine ont produit
    # le même jeu de données.
    campagne_empreinte: Mapped[str | None] = mapped_column(
        "CAMPAGNE_EMPREINTE", String(64)
    )
    campagne_fichier: Mapped[str | None] = mapped_column(
        "CAMPAGNE_FICHIER", String(255)
    )
    # Nul quand la campagne est créée hors de l'API (tests, script).
    utilisateur_uuid: Mapped[uuid.UUID | None] = mapped_column(
        "UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True)
    )


class CorrigeCampagne(AuditMixin, Base):
    """Le corrigé d'une campagne : une ligne par anomalie posée.

    C'est la pièce qui rend la mesure possible. Un outil de qualité branché sur
    des données réelles ne peut jamais dire combien de défauts lui ont échappé ;
    ici on le sait, parce qu'on les a posés soi-même et qu'on a noté où.

    La clé primaire porte l'invariant : un même type d'anomalie ne frappe
    qu'une fois une ligne donnée. Deux types différents peuvent en revanche
    viser le même champ — une date antidatée puis une date hors droits.
    """

    __tablename__ = "TB_CAMPAGNES_CORRIGE"
    __table_args__ = (
        Index("IX_CORRIGE_CAMPAGNE", "CAMPAGNE_ID"),
        Index("IX_CORRIGE_ANOMALIE", "CAMPAGNE_ID", "ANOMALIE_CODE"),
    )

    campagne_id: Mapped[uuid.UUID] = mapped_column(
        "CAMPAGNE_ID",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("TB_CAMPAGNES.CAMPAGNE_ID", ondelete="CASCADE"),
        primary_key=True,
    )
    # Numéro de ligne dans le fichier produit, à partir de 1 (l'en-tête ne
    # compte pas). Le rapport de l'outil testé s'y réfère.
    corrige_ligne: Mapped[int] = mapped_column(
        "CORRIGE_LIGNE", Integer, primary_key=True
    )
    anomalie_code: Mapped[str] = mapped_column(
        "ANOMALIE_CODE", String(50), primary_key=True
    )
    corrige_champ: Mapped[str] = mapped_column(
        "CORRIGE_CHAMP", String(60), nullable=False
    )
    # Les deux valeurs en texte : le corrigé décrit un fichier, pas des
    # colonnes typées, et une date « 32/13/2026 » n'entrerait dans aucun type.
    corrige_valeur_origine: Mapped[str] = mapped_column(
        "CORRIGE_VALEUR_ORIGINE", Text, nullable=False
    )
    corrige_valeur_injectee: Mapped[str] = mapped_column(
        "CORRIGE_VALEUR_INJECTEE", Text, nullable=False
    )
