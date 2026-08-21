"""Référentiels de valeurs repris du système CNAM : régimes et localisation.

Ces tables sont historisées : leur clé primaire porte la date de début de
validité, et DATE_FIN à NULL désigne la ligne en vigueur. Toute lecture doit
donc préciser à quelle date elle se place -- jamais « la ligne actuelle ».
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class Regime(AuditMixin, Base):
    """Un régime de couverture et son taux de remboursement."""

    __tablename__ = "TB_TV_REGIMES"
    __table_args__ = (
        CheckConstraint(
            '"REGIME_STATUT" IS NULL OR "REGIME_STATUT" IN (0, 1)',
            name="ck_regimes_statut",
        ),
        CheckConstraint('"REGIME_TAUX" BETWEEN 0 AND 100', name="ck_regimes_taux"),
    )

    regime_code: Mapped[str] = mapped_column("REGIME_CODE", String(3), primary_key=True)
    regime_date_debut: Mapped[datetime] = mapped_column(
        "REGIME_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    # RAM se rattache à RGB, et RGB se désigne lui-même : la racine de la
    # hiérarchie est son propre parent, aucune ligne n'a donc de parent nul.
    regime_code_parent: Mapped[str | None] = mapped_column("REGIME_CODE_PARENT", String(3))
    regime_denomination: Mapped[str] = mapped_column(
        "REGIME_DENOMINATION", String(100), nullable=False
    )
    regime_taux: Mapped[Decimal] = mapped_column("REGIME_TAUX", Numeric(5, 2), nullable=False)
    regime_date_fin: Mapped[datetime | None] = mapped_column(
        "REGIME_DATE_FIN", DateTime(timezone=True)
    )
    regime_statut: Mapped[int | None] = mapped_column("REGIME_STATUT", SmallInteger)


class Country(AuditMixin, Base):
    """Un pays du référentiel de localisation."""

    __tablename__ = "TB_TV_LOCALISATION_PAYS"
    __table_args__ = (
        CheckConstraint(
            '"PAYS_STATUT" IS NULL OR "PAYS_STATUT" IN (0, 1)', name="ck_pays_statut"
        ),
        Index("IX_PAYS_CODE", "PAYS_CODE"),
    )

    continent_code: Mapped[str] = mapped_column("CONTINENT_CODE", String(2), primary_key=True)
    pays_code: Mapped[str] = mapped_column("PAYS_CODE", String(3), primary_key=True)
    pays_date_debut: Mapped[datetime] = mapped_column(
        "PAYS_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    pays_code_numerique: Mapped[int] = mapped_column(
        "PAYS_CODE_NUMERIQUE", SmallInteger, nullable=False
    )
    pays_denomination: Mapped[str] = mapped_column(
        "PAYS_DENOMINATION", String(100), nullable=False
    )
    pays_gentile: Mapped[str] = mapped_column("PAYS_GENTILE", String(100), nullable=False)
    pays_indicatif: Mapped[int] = mapped_column("PAYS_INDICATIF", SmallInteger, nullable=False)
    pays_drapeau: Mapped[str | None] = mapped_column("PAYS_DRAPEAU", String(100))
    devise_code: Mapped[str] = mapped_column("DEVISE_CODE", String(3), nullable=False)
    pays_date_fin: Mapped[datetime | None] = mapped_column(
        "PAYS_DATE_FIN", DateTime(timezone=True)
    )
    pays_statut: Mapped[int | None] = mapped_column("PAYS_STATUT", SmallInteger)
    pays_latitude: Mapped[Decimal | None] = mapped_column("PAYS_LATITUDE", Numeric(9, 6))
    pays_longitude: Mapped[Decimal | None] = mapped_column("PAYS_LONGITUDE", Numeric(9, 6))


class Region(AuditMixin, Base):
    """Le premier niveau de découpage administratif d'un pays."""

    __tablename__ = "TB_TV_LOCALISATION_REGIONS"
    __table_args__ = (
        CheckConstraint(
            '"REGION_STATUT" IS NULL OR "REGION_STATUT" IN (0, 1)', name="ck_regions_statut"
        ),
        Index("IX_REGIONS_CODE", "REGION_CODE"),
    )

    pays_code: Mapped[str] = mapped_column("PAYS_CODE", String(3), primary_key=True)
    region_type: Mapped[str] = mapped_column("REGION_TYPE", String(1), primary_key=True)
    region_code: Mapped[str] = mapped_column("REGION_CODE", String(6), primary_key=True)
    region_date_debut: Mapped[datetime] = mapped_column(
        "REGION_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    region_denomination: Mapped[str] = mapped_column(
        "REGION_DENOMINATION", String(100), nullable=False
    )
    region_date_fin: Mapped[datetime | None] = mapped_column(
        "REGION_DATE_FIN", DateTime(timezone=True)
    )
    region_statut: Mapped[int | None] = mapped_column("REGION_STATUT", SmallInteger)
    region_latitude: Mapped[Decimal | None] = mapped_column("REGION_LATITUDE", Numeric(9, 6))
    region_longitude: Mapped[Decimal | None] = mapped_column("REGION_LONGITUDE", Numeric(9, 6))


class Department(AuditMixin, Base):
    """Le deuxième niveau de découpage, rattaché à une région.

    Aucune clé étrangère vers la région : la clé primaire de celle-ci compte
    quatre colonnes (pays, type, code, date de début) alors que cette table ne
    porte que le code. L'index remplace la contrainte, comme dans l'origine.
    """

    __tablename__ = "TB_TV_LOCALISATION_DEPARTEMENTS"
    __table_args__ = (
        CheckConstraint(
            '"DEPARTEMENT_STATUT" IS NULL OR "DEPARTEMENT_STATUT" IN (0, 1)',
            name="ck_departements_statut",
        ),
        Index("IX_DEPARTEMENTS_CODE", "DEPARTEMENT_CODE"),
    )

    region_code: Mapped[str] = mapped_column("REGION_CODE", String(6), primary_key=True)
    departement_type: Mapped[str] = mapped_column(
        "DEPARTEMENT_TYPE", String(1), primary_key=True
    )
    departement_code: Mapped[str] = mapped_column(
        "DEPARTEMENT_CODE", String(7), primary_key=True
    )
    departement_date_debut: Mapped[datetime] = mapped_column(
        "DEPARTEMENT_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    departement_denomination: Mapped[str] = mapped_column(
        "DEPARTEMENT_DENOMINATION", String(100), nullable=False
    )
    departement_date_fin: Mapped[datetime | None] = mapped_column(
        "DEPARTEMENT_DATE_FIN", DateTime(timezone=True)
    )
    departement_statut: Mapped[int | None] = mapped_column("DEPARTEMENT_STATUT", SmallInteger)
    departement_latitude: Mapped[Decimal | None] = mapped_column(
        "DEPARTEMENT_LATITUDE", Numeric(9, 6)
    )
    departement_longitude: Mapped[Decimal | None] = mapped_column(
        "DEPARTEMENT_LONGITUDE", Numeric(9, 6)
    )


class Locality(AuditMixin, Base):
    """Le niveau le plus fin : la localité où naît un assuré."""

    __tablename__ = "TB_TV_LOCALISATION_LOCALITES"
    __table_args__ = (
        CheckConstraint(
            '"LOCALITE_STATUT" IS NULL OR "LOCALITE_STATUT" IN (0, 1)',
            name="ck_localites_statut",
        ),
        Index("IX_LOCALITES_CODE", "LOCALITE_CODE"),
    )

    departement_code: Mapped[str] = mapped_column(
        "DEPARTEMENT_CODE", String(7), primary_key=True
    )
    localite_type: Mapped[str] = mapped_column("LOCALITE_TYPE", String(1), primary_key=True)
    localite_code: Mapped[str] = mapped_column("LOCALITE_CODE", String(8), primary_key=True)
    localite_date_debut: Mapped[datetime] = mapped_column(
        "LOCALITE_DATE_DEBUT", DateTime(timezone=True), primary_key=True
    )
    localite_denomination: Mapped[str] = mapped_column(
        "LOCALITE_DENOMINATION", String(100), nullable=False
    )
    localite_date_fin: Mapped[datetime | None] = mapped_column(
        "LOCALITE_DATE_FIN", DateTime(timezone=True)
    )
    localite_statut: Mapped[int | None] = mapped_column("LOCALITE_STATUT", SmallInteger)
    localite_latitude: Mapped[Decimal | None] = mapped_column("LOCALITE_LATITUDE", Numeric(9, 6))
    localite_longitude: Mapped[Decimal | None] = mapped_column(
        "LOCALITE_LONGITUDE", Numeric(9, 6)
    )
