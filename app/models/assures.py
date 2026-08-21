"""Tables satellites de l'assuré : identifiants, profession, naissance, droits.

Les trois premières sont historisées sur la même mécanique que les
référentiels : DATE_DEBUT dans la clé, DATE_FIN à NULL pour la ligne en cours.
Les droits, eux, sont découpés par mois calendaire.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base

if TYPE_CHECKING:
    from app.models.schema import InsuredPerson


class InsuredIdentifier(AuditMixin, Base):
    """Un identifiant porté par l'assuré pendant une période donnée."""

    __tablename__ = "TB_ASSURES_IDENTIFIANTS"
    __table_args__ = (Index("IX_IDENTIFIANTS_NUMERO", "IDENTIFIANT_NUMERO"),)

    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("TB_REF_ASSURES.PERSONNE_UUID"),
        primary_key=True,
    )
    type_identifiant_code: Mapped[str] = mapped_column(
        "TYPE_IDENTIFIANT_CODE", String(6), primary_key=True
    )
    identifiant_date_debut: Mapped[datetime] = mapped_column(
        "IDENTIFIANT_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    identifiant_numero: Mapped[str] = mapped_column(
        "IDENTIFIANT_NUMERO", String(100), nullable=False
    )
    identifiant_date_fin: Mapped[datetime | None] = mapped_column(
        "IDENTIFIANT_DATE_FIN", DateTime(timezone=True)
    )

    insured_person: Mapped["InsuredPerson"] = relationship(back_populates="identifiers")


class InsuredProfession(AuditMixin, Base):
    """La profession exercée par l'assuré pendant une période donnée."""

    __tablename__ = "TB_ASSURES_PROFESSIONS"

    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("TB_REF_ASSURES.PERSONNE_UUID"),
        primary_key=True,
    )
    profession_code: Mapped[str] = mapped_column(
        "PROFESSION_CODE", String(5), primary_key=True
    )
    profession_date_debut: Mapped[datetime] = mapped_column(
        "PROFESSION_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    profession_date_fin: Mapped[datetime | None] = mapped_column(
        "PROFESSION_DATE_FIN", DateTime(timezone=True)
    )

    insured_person: Mapped["InsuredPerson"] = relationship(back_populates="professions")


class InsuredBirthInfo(AuditMixin, Base):
    """Le lieu de naissance de l'assuré, chaîné jusqu'au pays.

    Attention au nom des colonnes : NAISSANCE_DATE_DEBUT est la date de début
    de validité de la ligne, pas la date de naissance -- celle-ci reste sur
    TB_REF_ASSURES.ASSURE_DATE_NAISSANCE.
    """

    __tablename__ = "TB_ASSURES_INFOS_NAISSANCE"
    __table_args__ = (Index("IX_NAISSANCE_LOCALITE", "LOCALITE_CODE"),)

    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("TB_REF_ASSURES.PERSONNE_UUID"),
        primary_key=True,
    )
    naissance_date_debut: Mapped[datetime] = mapped_column(
        "NAISSANCE_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    pays_code: Mapped[str] = mapped_column("PAYS_CODE", String(3), nullable=False)
    region_code: Mapped[str | None] = mapped_column("REGION_CODE", String(6))
    departement_code: Mapped[str | None] = mapped_column("DEPARTEMENT_CODE", String(7))
    localite_code: Mapped[str | None] = mapped_column("LOCALITE_CODE", String(8))
    code_postal: Mapped[str | None] = mapped_column("CODE_POSTAL", String(10))
    naissance_lieu: Mapped[str | None] = mapped_column("NAISSANCE_LIEU", String(50))
    naissance_date_fin: Mapped[datetime | None] = mapped_column(
        "NAISSANCE_DATE_FIN", DateTime(timezone=True)
    )

    insured_person: Mapped["InsuredPerson"] = relationship(back_populates="birth_info")


class InsuredRight(AuditMixin, Base):
    """L'état des droits de l'assuré pour un mois calendaire.

    DROITS_STATUT vaut 1 quand les droits sont ouverts et 0 quand ils sont
    fermés : c'est cette valeur, au mois des soins, qui autorise ou refuse
    la prise en charge d'une facture.
    """

    __tablename__ = "TB_ASSURES_DROITS"
    __table_args__ = (
        CheckConstraint('"DROITS_STATUT" IN (0, 1)', name="ck_droits_statut"),
        CheckConstraint('"DROITS_MOIS" BETWEEN 1 AND 12', name="ck_droits_mois"),
        CheckConstraint('"DROITS_ANNEE" BETWEEN 2000 AND 2100', name="ck_droits_annee"),
        Index("IX_DROITS_PERIODE_STATUT", "DROITS_ANNEE", "DROITS_MOIS", "DROITS_STATUT"),
    )

    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("TB_REF_ASSURES.PERSONNE_UUID"),
        primary_key=True,
    )
    droits_annee: Mapped[int] = mapped_column("DROITS_ANNEE", SmallInteger, primary_key=True)
    droits_mois: Mapped[int] = mapped_column("DROITS_MOIS", SmallInteger, primary_key=True)
    # Clé métier héritée du système d'origine : NOT NULL mais hors clé
    # primaire, on la garde unique pour qu'elle reste exploitable.
    droits_id: Mapped[str] = mapped_column(
        "DROITS_ID", String(100), nullable=False, unique=True
    )
    droits_statut: Mapped[int] = mapped_column("DROITS_STATUT", SmallInteger, nullable=False)
    droits_date_debut: Mapped[datetime] = mapped_column(
        "DROITS_DATE_DEBUT", DateTime(timezone=True), nullable=False
    )
    droits_date_fin: Mapped[datetime | None] = mapped_column(
        "DROITS_DATE_FIN", DateTime(timezone=True)
    )

    insured_person: Mapped["InsuredPerson"] = relationship(back_populates="rights")
