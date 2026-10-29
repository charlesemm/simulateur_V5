"""Modèles ORM du simulateur, posés sur le schéma de Mirka.

FICHIER GÉNÉRÉ — ne pas éditer à la main.
Régénérer avec : python tools/generer_modeles_orm.py

La correspondance entre ces classes et les tables de Mirka est déclarée dans
`app/models/correspondances.py`, qui en explique aussi les six arbitrages.

Les noms de classes sont ceux d'avant la bascule vers le schéma de Mirka : le
code qui importe `Invoice` ou `InsuredPerson` n'a pas eu à changer d'import.
Leurs colonnes, en revanche, sont celles de Mirka.

Les relations (`relationship`) ne sont pas générées : leurs noms d'attributs
ont été choisis à la main et ne se déduisent pas du schéma. Elles vivent dans
`app/models/relations.py`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, SimulationScopedMixin


class InsuredPerson(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ASSURES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ASSURES"

    personne_uuid: Mapped[str] = mapped_column(
        "PERSONNE_UUID",
        String(100),
        primary_key=True,
        autoincrement=False,
    )
    numero_recepisse: Mapped[str] = mapped_column("NUMERO_RECEPISSE", String(50), nullable=False)
    assure_numero_identifiant: Mapped[int | None] = mapped_column(
        "ASSURE_NUMERO_IDENTIFIANT",
        BigInteger,
    )
    numero_secu: Mapped[str | None] = mapped_column("NUMERO_SECU", String(52))
    civilite_code: Mapped[str] = mapped_column("CIVILITE_CODE", String(3), nullable=False)
    assure_nom: Mapped[str] = mapped_column("ASSURE_NOM", String(50), nullable=False)
    assure_nom_patronymique: Mapped[str | None] = mapped_column(
        "ASSURE_NOM_PATRONYMIQUE",
        String(50),
    )
    assure_prenoms: Mapped[str] = mapped_column("ASSURE_PRENOMS", String(150), nullable=False)
    genre_code: Mapped[str] = mapped_column("GENRE_CODE", String(1), nullable=False)
    assure_date_naissance: Mapped[datetime] = mapped_column(
        "ASSURE_DATE_NAISSANCE",
        DateTime(timezone=True),
        nullable=False,
    )
    assure_date_deces: Mapped[datetime | None] = mapped_column(
        "ASSURE_DATE_DECES",
        DateTime(timezone=True),
    )
    assure_rang_gemellaire: Mapped[int] = mapped_column(
        "ASSURE_RANG_GEMELLAIRE",
        SmallInteger,
        nullable=False,
        server_default=text("0"),
    )


class InsuredRight(SimulationScopedMixin, Base):
    """Table de faits Mirka TB_ASSURES_DROITS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ASSURES_DROITS"

    date_creation: Mapped[datetime] = mapped_column(
        "DATE_CREATION",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    droits_id: Mapped[str] = mapped_column("DROITS_ID", String(100), nullable=False)
    personne_uuid: Mapped[str] = mapped_column(
        "PERSONNE_UUID",
        String(100),
        ForeignKey("TB_SIM_ASSURES.PERSONNE_UUID"),
        primary_key=True,
        autoincrement=False,
    )
    droits_annee: Mapped[int] = mapped_column(
        "DROITS_ANNEE",
        SmallInteger,
        primary_key=True,
        autoincrement=False,
    )
    droits_mois: Mapped[int] = mapped_column(
        "DROITS_MOIS",
        SmallInteger,
        primary_key=True,
        autoincrement=False,
    )
    droits_statut: Mapped[int] = mapped_column("DROITS_STATUT", SmallInteger, nullable=False)
    droits_date_debut: Mapped[datetime] = mapped_column(
        "DROITS_DATE_DEBUT",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    droits_date_fin: Mapped[datetime | None] = mapped_column(
        "DROITS_DATE_FIN",
        DateTime(timezone=True),
    )


class InsuredIdentifier(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ASSURES_IDENTIFIANTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ASSURES_IDENTIFIANTS"

    personne_uuid: Mapped[str] = mapped_column(
        "PERSONNE_UUID",
        String(100),
        ForeignKey("TB_SIM_ASSURES.PERSONNE_UUID"),
        primary_key=True,
        autoincrement=False,
    )
    type_identifiant_code: Mapped[str] = mapped_column(
        "TYPE_IDENTIFIANT_CODE",
        String(6),
        primary_key=True,
        autoincrement=False,
    )
    identifiant_numero: Mapped[str] = mapped_column(
        "IDENTIFIANT_NUMERO",
        String(100),
        nullable=False,
    )
    identifiant_date_debut: Mapped[datetime] = mapped_column(
        "IDENTIFIANT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    identifiant_date_fin: Mapped[datetime | None] = mapped_column(
        "IDENTIFIANT_DATE_FIN",
        DateTime(timezone=True),
    )


class InsuredBirthInfo(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ASSURES_INFOS_NAISSANCE, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ASSURES_INFOS_NAISSANCE"

    personne_uuid: Mapped[str] = mapped_column(
        "PERSONNE_UUID",
        String(100),
        ForeignKey("TB_SIM_ASSURES.PERSONNE_UUID"),
        primary_key=True,
        autoincrement=False,
    )
    pays_code: Mapped[str] = mapped_column("PAYS_CODE", String(3), nullable=False)
    region_code: Mapped[str | None] = mapped_column("REGION_CODE", String(6))
    departement_code: Mapped[str | None] = mapped_column("DEPARTEMENT_CODE", String(7))
    localite_code: Mapped[str | None] = mapped_column("LOCALITE_CODE", String(8))
    code_postal: Mapped[str | None] = mapped_column("CODE_POSTAL", String(10))
    naissance_lieu: Mapped[str | None] = mapped_column("NAISSANCE_LIEU", String(50))
    naissance_date_debut: Mapped[datetime] = mapped_column(
        "NAISSANCE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    naissance_date_fin: Mapped[datetime | None] = mapped_column(
        "NAISSANCE_DATE_FIN",
        DateTime(timezone=True),
    )


class InsuredProfession(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ASSURES_PROFESSIONS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ASSURES_PROFESSIONS"

    personne_uuid: Mapped[str] = mapped_column(
        "PERSONNE_UUID",
        String(100),
        ForeignKey("TB_SIM_ASSURES.PERSONNE_UUID"),
        primary_key=True,
        autoincrement=False,
    )
    profession_code: Mapped[str] = mapped_column(
        "PROFESSION_CODE",
        String(5),
        primary_key=True,
        autoincrement=False,
    )
    profession_date_debut: Mapped[datetime] = mapped_column(
        "PROFESSION_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    profession_date_fin: Mapped[datetime | None] = mapped_column(
        "PROFESSION_DATE_FIN",
        DateTime(timezone=True),
    )


class HealthCenter(AuditMixin, Base):
    """Référentiel Mirka TB_REF_CENTRES_SANTE, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_CENTRES_SANTE"

    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    collectivite_code: Mapped[str | None] = mapped_column("COLLECTIVITE_CODE", String(10))
    type_etablissement_sanitaire_code: Mapped[str | None] = mapped_column(
        "TYPE_ETABLISSEMENT_SANITAIRE_CODE",
        String(3),
    )
    centre_sante_numero_immatriculation: Mapped[str | None] = mapped_column(
        "CENTRE_SANTE_NUMERO_IMMATRICULATION",
        String(20),
    )
    centre_sante_denomination: Mapped[str] = mapped_column(
        "CENTRE_SANTE_DENOMINATION",
        String(1000),
        nullable=False,
    )
    secteur_activite_code: Mapped[str | None] = mapped_column("SECTEUR_ACTIVITE_CODE", String(4))
    centre_sante_logo: Mapped[str | None] = mapped_column("CENTRE_SANTE_LOGO", String(100))
    centre_sante_statut: Mapped[int | None] = mapped_column("CENTRE_SANTE_STATUT", SmallInteger)
    centre_sante_logo_format: Mapped[str | None] = mapped_column(
        "CENTRE_SANTE_LOGO_FORMAT",
        String(50),
    )


class Collectivite(AuditMixin, Base):
    """Référentiel Mirka TB_REF_COLLECTIVITES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_COLLECTIVITES"

    collectivite_code: Mapped[str] = mapped_column(
        "COLLECTIVITE_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    collectivite_numero_immatriculation: Mapped[str | None] = mapped_column(
        "COLLECTIVITE_NUMERO_IMMATRICULATION",
        String(20),
    )
    collectivite_denomination: Mapped[str] = mapped_column(
        "COLLECTIVITE_DENOMINATION",
        String(150),
        nullable=False,
    )
    collectivite_numero_siret: Mapped[str | None] = mapped_column(
        "COLLECTIVITE_NUMERO_SIRET",
        String(14),
    )
    forme_juridique_code: Mapped[str | None] = mapped_column("FORME_JURIDIQUE_CODE", String(4))
    secteur_activite_code: Mapped[str | None] = mapped_column("SECTEUR_ACTIVITE_CODE", String(5))
    domaine_activite_code: Mapped[str | None] = mapped_column("DOMAINE_ACTIVITE_CODE", String(5))
    collectivite_logo: Mapped[bytes | None] = mapped_column("COLLECTIVITE_LOGO", LargeBinary)
    collectivite_logo_mime: Mapped[str | None] = mapped_column("COLLECTIVITE_LOGO_MIME", String(50))
    collectivite_statut: Mapped[int | None] = mapped_column("COLLECTIVITE_STATUT", SmallInteger)


class CollectiviteAddress(AuditMixin, Base):
    """Référentiel Mirka TB_REF_COLLECTIVITES_ADRESSES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_COLLECTIVITES_ADRESSES"

    collectivite_code: Mapped[str] = mapped_column(
        "COLLECTIVITE_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    pays_code: Mapped[str] = mapped_column("PAYS_CODE", String(3), nullable=False)
    region_code: Mapped[str | None] = mapped_column("REGION_CODE", String(6))
    departement_code: Mapped[str | None] = mapped_column("DEPARTEMENT_CODE", String(7))
    localite_code: Mapped[str | None] = mapped_column("LOCALITE_CODE", String(8))
    adresse_postale: Mapped[str | None] = mapped_column("ADRESSE_POSTALE", String(38))
    adresse_geographique: Mapped[str | None] = mapped_column("ADRESSE_GEOGRAPHIQUE", String(250))
    adresse_geographique_complement: Mapped[str | None] = mapped_column(
        "ADRESSE_GEOGRAPHIQUE_COMPLEMENT",
        String(100),
    )
    adresse_code_postal: Mapped[str | None] = mapped_column("ADRESSE_CODE_POSTAL", String(10))
    adresse_latitude: Mapped[str | None] = mapped_column("ADRESSE_LATITUDE", String(100))
    adresse_longitude: Mapped[str | None] = mapped_column("ADRESSE_LONGITUDE", String(100))
    adresse_date_debut: Mapped[datetime] = mapped_column(
        "ADRESSE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    adresse_date_fin: Mapped[datetime | None] = mapped_column(
        "ADRESSE_DATE_FIN",
        DateTime(timezone=True),
    )


class Agent(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_AGENTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_AGENTS"

    agent_code: Mapped[str] = mapped_column(
        "AGENT_CODE",
        String(8),
        primary_key=True,
        autoincrement=False,
    )
    agent_code_gestion: Mapped[str | None] = mapped_column("AGENT_CODE_GESTION", String(8))
    agent_prenoms: Mapped[str] = mapped_column("AGENT_PRENOMS", String(80), nullable=False)
    agent_nom: Mapped[str] = mapped_column("AGENT_NOM", String(50), nullable=False)
    agent_email: Mapped[str | None] = mapped_column("AGENT_EMAIL", String(100))
    agent_statut: Mapped[int | None] = mapped_column("AGENT_STATUT", SmallInteger)
    agent_date_debut: Mapped[datetime] = mapped_column(
        "AGENT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    agent_date_fin: Mapped[datetime | None] = mapped_column(
        "AGENT_DATE_FIN",
        DateTime(timezone=True),
    )


class CenterHealthAgent(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_CENTRES_SANTE_AGENTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_CENTRES_SANTE_AGENTS"

    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    agent_code: Mapped[str] = mapped_column(
        "AGENT_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    centre_sante_agent_debut: Mapped[datetime] = mapped_column(
        "CENTRE_SANTE_AGENT_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    centre_sante_agent_fin: Mapped[datetime | None] = mapped_column(
        "CENTRE_SANTE_AGENT_FIN",
        DateTime(timezone=True),
    )


class HealthProfessional(AuditMixin, Base):
    """Référentiel Mirka TB_REF_PROFESSIONNELS_SANTE, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_PROFESSIONNELS_SANTE"

    personne_uuid: Mapped[str | None] = mapped_column(
        "PERSONNE_UUID",
        String(100),
        ForeignKey("TB_SIM_ASSURES.PERSONNE_UUID"),
    )
    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    civilite_code: Mapped[str] = mapped_column("CIVILITE_CODE", String(3), nullable=False)
    professionnel_sante_nom: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_NOM",
        String(30),
        nullable=False,
    )
    professionnel_sante_prenoms: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_PRENOMS",
        String(50),
        nullable=False,
    )
    professionnel_sante_date_naissance: Mapped[datetime | None] = mapped_column(
        "PROFESSIONNEL_SANTE_DATE_NAISSANCE",
        DateTime(timezone=True),
    )
    genre_code: Mapped[str] = mapped_column("GENRE_CODE", String(1), nullable=False)
    professionnel_sante_num_immatriculation: Mapped[str | None] = mapped_column(
        "PROFESSIONNEL_SANTE_NUM_IMMATRICULATION",
        String(15),
    )
    professionnel_sante_photo: Mapped[bytes | None] = mapped_column(
        "PROFESSIONNEL_SANTE_PHOTO",
        LargeBinary,
    )
    professionnel_sante_photo_format: Mapped[str | None] = mapped_column(
        "PROFESSIONNEL_SANTE_PHOTO_FORMAT",
        String(50),
    )
    professionnel_sante_statut: Mapped[int | None] = mapped_column(
        "PROFESSIONNEL_SANTE_STATUT",
        SmallInteger,
    )


class MedicalSpecialty(AuditMixin, Base):
    """Référentiel Mirka TB_TV_SPECIALITES_MEDICALES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_SPECIALITES_MEDICALES"

    specialite_medicale_code: Mapped[str] = mapped_column(
        "SPECIALITE_MEDICALE_CODE",
        String(2),
        primary_key=True,
        autoincrement=False,
    )
    specialite_medicale_denomination: Mapped[str] = mapped_column(
        "SPECIALITE_MEDICALE_DENOMINATION",
        String(100),
        nullable=False,
    )
    specialite_medicale_date_debut: Mapped[datetime] = mapped_column(
        "SPECIALITE_MEDICALE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    specialite_medicale_date_fin: Mapped[datetime | None] = mapped_column(
        "SPECIALITE_MEDICALE_DATE_FIN",
        DateTime(timezone=True),
    )
    specialite_medicale_statut: Mapped[int | None] = mapped_column(
        "SPECIALITE_MEDICALE_STATUT",
        SmallInteger,
    )


class HealthProfessionalMedicalSpecialty(AuditMixin, Base):
    """Référentiel Mirka TB_REF_PROFESSIONNELS_SANTE_SPECIALITES_MEDICALES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_PROFESSIONNELS_SANTE_SPECIALITES_MEDICALES"

    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        String(9),
        ForeignKey("TB_SIM_REF_PROFESSIONNELS_SANTE.PROFESSIONNEL_SANTE_CODE"),
        primary_key=True,
        autoincrement=False,
    )
    specialite_medicale_code: Mapped[str] = mapped_column(
        "SPECIALITE_MEDICALE_CODE",
        String(2),
        primary_key=True,
        autoincrement=False,
    )
    specialite_medicale_date_debut: Mapped[datetime] = mapped_column(
        "SPECIALITE_MEDICALE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    specialite_medicale_date_fin: Mapped[datetime | None] = mapped_column(
        "SPECIALITE_MEDICALE_DATE_FIN",
        DateTime(timezone=True),
    )


class HealthProfessionalCenter(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_CENTRES_SANTE_PROFESSIONNELS_SANTE, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_CENTRES_SANTE_PROFESSIONNELS_SANTE"

    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    centre_sante_professionnel_sante_date_debut: Mapped[datetime] = mapped_column(
        "CENTRE_SANTE_PROFESSIONNEL_SANTE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    centre_sante_professionnel_sante_date_fin: Mapped[datetime | None] = mapped_column(
        "CENTRE_SANTE_PROFESSIONNEL_SANTE_DATE_FIN",
        DateTime(timezone=True),
    )
    centre_sante_professionnel_sante_statut: Mapped[int | None] = mapped_column(
        "CENTRE_SANTE_PROFESSIONNEL_SANTE_STATUT",
        SmallInteger,
    )


class Pathology(AuditMixin, Base):
    """Référentiel Mirka TB_REF_PATHOLOGIES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_PATHOLOGIES"

    sous_chapitre_code: Mapped[str | None] = mapped_column("SOUS_CHAPITRE_CODE", String(7))
    pathologie_code: Mapped[str] = mapped_column(
        "PATHOLOGIE_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    pathologie_denomination: Mapped[str] = mapped_column(
        "PATHOLOGIE_DENOMINATION",
        String(200),
        nullable=False,
    )
    pathologie_date_debut: Mapped[datetime] = mapped_column(
        "PATHOLOGIE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    pathologie_date_fin: Mapped[datetime | None] = mapped_column(
        "PATHOLOGIE_DATE_FIN",
        DateTime(timezone=True),
    )
    pathologie_statut: Mapped[int | None] = mapped_column("PATHOLOGIE_STATUT", SmallInteger)


class Medication(AuditMixin, Base):
    """Référentiel Mirka TB_REF_MEDICAMENTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_MEDICAMENTS"

    type_code: Mapped[str] = mapped_column("TYPE_CODE", String(6), nullable=False)
    medicament_code: Mapped[str] = mapped_column(
        "MEDICAMENT_CODE",
        String(20),
        primary_key=True,
        autoincrement=False,
    )
    medicament_denomination: Mapped[str] = mapped_column(
        "MEDICAMENT_DENOMINATION",
        String(150),
        nullable=False,
    )
    medicament_ean13: Mapped[str | None] = mapped_column("MEDICAMENT_EAN13", String(30))
    dci_code: Mapped[str] = mapped_column("DCI_CODE", String(20), nullable=False)
    laboratoire_code: Mapped[str] = mapped_column("LABORATOIRE_CODE", String(6), nullable=False)
    famille_forme_code: Mapped[str] = mapped_column("FAMILLE_FORME_CODE", String(6), nullable=False)
    conditionnement_code: Mapped[str] = mapped_column(
        "CONDITIONNEMENT_CODE",
        String(6),
        nullable=False,
    )
    presentation_code: Mapped[str] = mapped_column("PRESENTATION_CODE", String(5), nullable=False)
    liste_types_factures: Mapped[str] = mapped_column(
        "LISTE_TYPES_FACTURES",
        String(1000),
        nullable=False,
    )
    liste_genres: Mapped[str] = mapped_column("LISTE_GENRES", String(100), nullable=False)
    medicament_quantite_maximum: Mapped[int] = mapped_column(
        "MEDICAMENT_QUANTITE_MAXIMUM",
        BigInteger,
        nullable=False,
    )
    medicament_age_minimum: Mapped[int] = mapped_column(
        "MEDICAMENT_AGE_MINIMUM",
        BigInteger,
        nullable=False,
    )
    medicament_age_maximum: Mapped[int] = mapped_column(
        "MEDICAMENT_AGE_MAXIMUM",
        BigInteger,
        nullable=False,
    )
    medicament_hapax_statut: Mapped[int] = mapped_column(
        "MEDICAMENT_HAPAX_STATUT",
        SmallInteger,
        nullable=False,
    )
    medicament_tarif_defaut: Mapped[int | None] = mapped_column(
        "MEDICAMENT_TARIF_DEFAUT",
        BigInteger,
    )
    medicament_statut: Mapped[int | None] = mapped_column("MEDICAMENT_STATUT", SmallInteger)
    medicament_date_debut: Mapped[datetime] = mapped_column(
        "MEDICAMENT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    medicament_date_fin: Mapped[datetime | None] = mapped_column(
        "MEDICAMENT_DATE_FIN",
        DateTime(timezone=True),
    )


class Dci(AuditMixin, Base):
    """Référentiel Mirka TB_REF_MEDICAMENTS_DCI, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_MEDICAMENTS_DCI"

    dci_code: Mapped[str] = mapped_column(
        "DCI_CODE",
        String(20),
        primary_key=True,
        autoincrement=False,
    )
    dci_denomination: Mapped[str] = mapped_column("DCI_DENOMINATION", String(100), nullable=False)
    dosage: Mapped[str] = mapped_column("DOSAGE", String(30), nullable=False)
    forme_code: Mapped[str] = mapped_column("FORME_CODE", String(4), nullable=False)
    classification_detaillee_code: Mapped[str] = mapped_column(
        "CLASSIFICATION_DETAILLEE_CODE",
        String(15),
        nullable=False,
    )
    forme_administration_code: Mapped[str] = mapped_column(
        "FORME_ADMINISTRATION_CODE",
        String(10),
        nullable=False,
    )
    dci_molecule: Mapped[str] = mapped_column("DCI_MOLECULE", String(100), nullable=False)
    dci_date_debut: Mapped[datetime] = mapped_column(
        "DCI_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    dci_date_fin: Mapped[datetime | None] = mapped_column("DCI_DATE_FIN", DateTime(timezone=True))
    dci_statut: Mapped[Decimal | None] = mapped_column("DCI_STATUT", Numeric)


class MedicalAct(AuditMixin, Base):
    """Référentiel Mirka TB_REF_ACTES_MEDICAUX, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_REF_ACTES_MEDICAUX"

    article_code: Mapped[str | None] = mapped_column("ARTICLE_CODE", String(7))
    acte_medical_type: Mapped[str | None] = mapped_column("ACTE_MEDICAL_TYPE", String(10))
    acte_medical_code: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_CODE",
        String(7),
        primary_key=True,
        autoincrement=False,
    )
    acte_medical_denomination: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_DENOMINATION",
        String(1000),
        nullable=False,
    )
    liste_types_factures: Mapped[str] = mapped_column(
        "LISTE_TYPES_FACTURES",
        String(1000),
        nullable=False,
    )
    liste_genres: Mapped[str] = mapped_column("LISTE_GENRES", String(100), nullable=False)
    acte_medical_age_minimum: Mapped[int] = mapped_column(
        "ACTE_MEDICAL_AGE_MINIMUM",
        BigInteger,
        nullable=False,
    )
    acte_medical_age_maximum: Mapped[int] = mapped_column(
        "ACTE_MEDICAL_AGE_MAXIMUM",
        BigInteger,
        nullable=False,
    )
    acte_medical_quantite_maximum: Mapped[int] = mapped_column(
        "ACTE_MEDICAL_QUANTITE_MAXIMUM",
        BigInteger,
        nullable=False,
    )
    acte_medical_hapax_statut: Mapped[int] = mapped_column(
        "ACTE_MEDICAL_HAPAX_STATUT",
        SmallInteger,
        nullable=False,
    )
    acte_medical_statut: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_STATUT",
        SmallInteger,
        server_default=text("0"),
    )
    acte_medical_date_debut: Mapped[datetime] = mapped_column(
        "ACTE_MEDICAL_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    acte_medical_date_fin: Mapped[datetime | None] = mapped_column(
        "ACTE_MEDICAL_DATE_FIN",
        DateTime(timezone=True),
    )


class TypeInvoice(AuditMixin, Base):
    """Référentiel Mirka TB_TV_TYPES_FACTURES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_TYPES_FACTURES"

    type_facture_code: Mapped[str] = mapped_column(
        "TYPE_FACTURE_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    type_facture_denomination: Mapped[str | None] = mapped_column(
        "TYPE_FACTURE_DENOMINATION",
        String(100),
    )
    type_facture_date_debut: Mapped[datetime] = mapped_column(
        "TYPE_FACTURE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    type_facture_date_fin: Mapped[datetime | None] = mapped_column(
        "TYPE_FACTURE_DATE_FIN",
        DateTime(timezone=True),
    )
    type_facture_statut: Mapped[Decimal | None] = mapped_column("TYPE_FACTURE_STATUT", Numeric)


class Invoice(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES"

    produit_code: Mapped[str] = mapped_column("PRODUIT_CODE", String(10), nullable=False)
    regime_code: Mapped[str] = mapped_column("REGIME_CODE", String(3), nullable=False)
    regime_taux: Mapped[Decimal] = mapped_column("REGIME_TAUX", Numeric(4, 1), nullable=False)
    organisme_code: Mapped[str | None] = mapped_column("ORGANISME_CODE", String(8))
    assurance_code: Mapped[str | None] = mapped_column("ASSURANCE_CODE", String(8))
    personne_uuid: Mapped[str] = mapped_column("PERSONNE_UUID", String(100), nullable=False)
    type_facture_code: Mapped[str | None] = mapped_column("TYPE_FACTURE_CODE", String(9))
    facture_date_soins: Mapped[datetime] = mapped_column(
        "FACTURE_DATE_SOINS",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    dossier_numero: Mapped[Decimal | None] = mapped_column("DOSSIER_NUMERO", Numeric(38, 0))
    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        primary_key=True,
        autoincrement=False,
    )
    centre_sante_code: Mapped[str] = mapped_column("CENTRE_SANTE_CODE", String(9), nullable=False)
    centre_sante_type_code: Mapped[str | None] = mapped_column("CENTRE_SANTE_TYPE_CODE", String(1))
    centre_sante_type_libelle: Mapped[str | None] = mapped_column(
        "CENTRE_SANTE_TYPE_LIBELLE",
        String(100),
    )
    reseau_code: Mapped[str] = mapped_column("RESEAU_CODE", String(10), nullable=False)
    entente_prealable_id: Mapped[str | None] = mapped_column("ENTENTE_PREALABLE_ID", String(100))


class InvoicePathology(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES_PATHOLOGIES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES_PATHOLOGIES"

    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        primary_key=True,
        autoincrement=False,
    )
    pathologie_code: Mapped[str] = mapped_column(
        "PATHOLOGIE_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    pathologie_observations: Mapped[str | None] = mapped_column(
        "PATHOLOGIE_OBSERVATIONS",
        String(100),
    )
    pathologie_date_debut: Mapped[datetime] = mapped_column(
        "PATHOLOGIE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    pathologie_date_fin: Mapped[datetime | None] = mapped_column(
        "PATHOLOGIE_DATE_FIN",
        DateTime(timezone=True),
    )


class InvoicePrescription(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES_PRESCRIPTIONS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES_PRESCRIPTIONS"

    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        ForeignKey("TB_SIM_FACTURES.FACTURE_NUMERO"),
        primary_key=True,
        autoincrement=False,
    )
    prescription_code: Mapped[str] = mapped_column(
        "PRESCRIPTION_CODE",
        String(50),
        primary_key=True,
        autoincrement=False,
    )
    prescription_quantite: Mapped[Decimal] = mapped_column(
        "PRESCRIPTION_QUANTITE",
        Numeric(38, 0),
        nullable=False,
    )
    prescription_posologie: Mapped[str | None] = mapped_column(
        "PRESCRIPTION_POSOLOGIE",
        String(2000),
    )
    prescription_duree: Mapped[str | None] = mapped_column("PRESCRIPTION_DUREE", String(100))
    prescription_renseignements_cliniques: Mapped[str | None] = mapped_column(
        "PRESCRIPTION_RENSEIGNEMENTS_CLINIQUES",
        String(2000),
    )
    date_debut: Mapped[datetime] = mapped_column(
        "DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    date_fin: Mapped[datetime | None] = mapped_column("DATE_FIN", DateTime(timezone=True))


class InvoiceProvision(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES_PRESTATIONS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES_PRESTATIONS"

    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        ForeignKey("TB_SIM_FACTURES.FACTURE_NUMERO"),
        primary_key=True,
        autoincrement=False,
    )
    prestation_code: Mapped[str] = mapped_column(
        "PRESTATION_CODE",
        String(50),
        primary_key=True,
        autoincrement=False,
    )
    statut_remboursement: Mapped[int] = mapped_column(
        "STATUT_REMBOURSEMENT",
        SmallInteger,
        nullable=False,
    )
    motif_non_remboursement: Mapped[str | None] = mapped_column(
        "MOTIF_NON_REMBOURSEMENT",
        String(1000),
    )
    prestation_base_remboursement: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_BASE_REMBOURSEMENT",
        Numeric(10, 2),
    )
    prestation_taux_remboursement: Mapped[int | None] = mapped_column(
        "PRESTATION_TAUX_REMBOURSEMENT",
        SmallInteger,
    )
    prestation_quantite_prescrite: Mapped[int | None] = mapped_column(
        "PRESTATION_QUANTITE_PRESCRITE",
        BigInteger,
    )
    prestation_quantite_servie: Mapped[int | None] = mapped_column(
        "PRESTATION_QUANTITE_SERVIE",
        BigInteger,
    )
    prestation_prix_unitaire: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_PRIX_UNITAIRE",
        Numeric(10, 2),
    )
    prestation_montant_depense: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_DEPENSE",
        Numeric(10, 2),
    )
    prestation_montant_rgb: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_RGB",
        Numeric(10, 2),
    )
    prestation_montant_complementaire: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_COMPLEMENTAIRE",
        Numeric(10, 2),
    )
    prestation_montant_remise: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_REMISE",
        Numeric(10, 2),
    )
    prestation_montant_assure: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_ASSURE",
        Numeric(10, 2),
    )
    prestation_date_debut: Mapped[datetime] = mapped_column(
        "PRESTATION_DATE_DEBUT",
        DateTime(timezone=True),
        nullable=False,
    )
    prestation_date_fin: Mapped[datetime] = mapped_column(
        "PRESTATION_DATE_FIN",
        DateTime(timezone=True),
        nullable=False,
    )
    dents_numeros: Mapped[str | None] = mapped_column("DENTS_NUMEROS", String(500))
    statut_code: Mapped[str | None] = mapped_column("STATUT_CODE", String(1))
    motif_rejet_code: Mapped[str | None] = mapped_column("MOTIF_REJET_CODE", String(10))
    prestation_observations: Mapped[str | None] = mapped_column(
        "PRESTATION_OBSERVATIONS",
        String(1000),
    )
    date_debut: Mapped[datetime] = mapped_column(
        "DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    date_fin: Mapped[datetime | None] = mapped_column("DATE_FIN", DateTime(timezone=True))


class InvoiceRejection(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES_REJETS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES_REJETS"

    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        ForeignKey("TB_SIM_FACTURES.FACTURE_NUMERO"),
        primary_key=True,
        autoincrement=False,
    )
    rejet_code: Mapped[str] = mapped_column(
        "REJET_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    rejet_date_debut: Mapped[datetime] = mapped_column(
        "REJET_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    rejet_date_fin: Mapped[datetime | None] = mapped_column(
        "REJET_DATE_FIN",
        DateTime(timezone=True),
    )


class InvoiceStatus(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES_STATUTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES_STATUTS"

    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        primary_key=True,
        autoincrement=False,
    )
    statut_code: Mapped[str] = mapped_column(
        "STATUT_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    statut_observations: Mapped[str | None] = mapped_column("STATUT_OBSERVATIONS", String(100))
    statut_date_debut: Mapped[datetime] = mapped_column(
        "STATUT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    statut_date_fin: Mapped[datetime | None] = mapped_column(
        "STATUT_DATE_FIN",
        DateTime(timezone=True),
    )


class PriorAuthorization(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ENTENTES_PREALABLES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ENTENTES_PREALABLES"

    entente_prealable_id: Mapped[str] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        String(100),
        primary_key=True,
        autoincrement=False,
    )
    entente_prealable_numero: Mapped[Decimal] = mapped_column(
        "ENTENTE_PREALABLE_NUMERO",
        Numeric(28, 0),
        nullable=False,
    )
    centre_sante_code: Mapped[str] = mapped_column("CENTRE_SANTE_CODE", String(9), nullable=False)
    personne_uuid: Mapped[str] = mapped_column("PERSONNE_UUID", String(150), nullable=False)
    dossier_numero: Mapped[Decimal] = mapped_column(
        "DOSSIER_NUMERO",
        Numeric(38, 0),
        nullable=False,
    )
    entente_prealable_date_debut: Mapped[datetime] = mapped_column(
        "ENTENTE_PREALABLE_DATE_DEBUT",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    entente_prealable_date_fin: Mapped[datetime | None] = mapped_column(
        "ENTENTE_PREALABLE_DATE_FIN",
        DateTime(timezone=True),
    )
    entente_prealable_numero_organisme: Mapped[str | None] = mapped_column(
        "ENTENTE_PREALABLE_NUMERO_ORGANISME",
        String(100),
    )
    organisme_code: Mapped[str] = mapped_column("ORGANISME_CODE", String(8), nullable=False)
    facture_numero: Mapped[Decimal | None] = mapped_column("FACTURE_NUMERO", Numeric(38, 0))
    type_demande_code: Mapped[str] = mapped_column("TYPE_DEMANDE_CODE", String(5), nullable=False)
    type_hospitalisation_code: Mapped[str | None] = mapped_column(
        "TYPE_HOSPITALISATION_CODE",
        String(5),
    )


class PriorAuthorizationStatus(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ENTENTES_PREALABLES_STATUTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ENTENTES_PREALABLES_STATUTS"

    entente_prealable_id: Mapped[str] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        String(100),
        primary_key=True,
        autoincrement=False,
    )
    statut_code: Mapped[str] = mapped_column(
        "STATUT_CODE",
        String(5),
        primary_key=True,
        autoincrement=False,
    )
    statut_date_debut: Mapped[datetime] = mapped_column(
        "STATUT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    statut_date_fin: Mapped[datetime | None] = mapped_column(
        "STATUT_DATE_FIN",
        DateTime(timezone=True),
    )


class PriorAuthorizationMedicalAct(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ENTENTES_PREALABLES_ACTES_MEDICAUX, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ENTENTES_PREALABLES_ACTES_MEDICAUX"

    entente_prealable_id: Mapped[str] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        String(100),
        primary_key=True,
        autoincrement=False,
    )
    acte_medical_code: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_CODE",
        String(7),
        primary_key=True,
        autoincrement=False,
    )
    acte_medical_motif: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_MOTIF",
        String(1000),
        nullable=False,
    )
    acte_medical_base_remboursement: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_BASE_REMBOURSEMENT",
        BigInteger,
    )
    acte_medical_taux_remboursement: Mapped[int] = mapped_column(
        "ACTE_MEDICAL_TAUX_REMBOURSEMENT",
        SmallInteger,
        nullable=False,
    )
    acte_medical_montant_cmu: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_MONTANT_CMU",
        BigInteger,
    )
    acte_medical_montant_assure: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_MONTANT_ASSURE",
        BigInteger,
    )
    acte_medical_statut: Mapped[str | None] = mapped_column("ACTE_MEDICAL_STATUT", String(3))
    acte_medical_motif_rejet: Mapped[str | None] = mapped_column(
        "ACTE_MEDICAL_MOTIF_REJET",
        String(1000),
    )


class PriorAuthorizationProvision(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_ENTENTES_PREALABLES_PRESTATIONS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_ENTENTES_PREALABLES_PRESTATIONS"

    entente_prealable_id: Mapped[str] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        String(100),
        primary_key=True,
        autoincrement=False,
    )
    prestation_code: Mapped[str] = mapped_column(
        "PRESTATION_CODE",
        String(7),
        primary_key=True,
        autoincrement=False,
    )
    prestation_motif: Mapped[str] = mapped_column("PRESTATION_MOTIF", String(1000), nullable=False)
    prestation_prix_unitaire: Mapped[int] = mapped_column(
        "PRESTATION_PRIX_UNITAIRE",
        BigInteger,
        nullable=False,
    )
    prestation_quantite: Mapped[int] = mapped_column(
        "PRESTATION_QUANTITE",
        BigInteger,
        nullable=False,
    )
    prestation_statut: Mapped[str | None] = mapped_column("PRESTATION_STATUT", String(3))
    prestation_motif_rejet: Mapped[str | None] = mapped_column(
        "PRESTATION_MOTIF_REJET",
        String(1000),
    )


class InsuredEntitlement(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_DROITS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_DROITS"

    droits_id: Mapped[str] = mapped_column(
        "DROITS_ID",
        String(100),
        primary_key=True,
        autoincrement=False,
    )
    droits_delai_carence: Mapped[int] = mapped_column(
        "DROITS_DELAI_CARENCE",
        BigInteger,
        nullable=False,
    )
    produit_code: Mapped[str] = mapped_column("PRODUIT_CODE", String(10), nullable=False)
    organisme_code: Mapped[str | None] = mapped_column("ORGANISME_CODE", String(8))
    categorie_socio_professionnelle_code: Mapped[str | None] = mapped_column(
        "CATEGORIE_SOCIO_PROFESSIONNELLE_CODE",
        String(3),
    )
    collectivite_code: Mapped[str | None] = mapped_column("COLLECTIVITE_CODE", String(10))
    personne_uuid: Mapped[str | None] = mapped_column("PERSONNE_UUID", String(100))
    droits_statut: Mapped[int] = mapped_column("DROITS_STATUT", SmallInteger, nullable=False)
    droits_motif: Mapped[str] = mapped_column("DROITS_MOTIF", String(3000), nullable=False)
    droits_validite_date_debut: Mapped[datetime | None] = mapped_column(
        "DROITS_VALIDITE_DATE_DEBUT",
        DateTime(timezone=True),
    )
    droits_validite_date_fin: Mapped[datetime | None] = mapped_column(
        "DROITS_VALIDITE_DATE_FIN",
        DateTime(timezone=True),
    )
    droits_date_debut: Mapped[datetime] = mapped_column(
        "DROITS_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    droits_date_fin: Mapped[datetime | None] = mapped_column(
        "DROITS_DATE_FIN",
        DateTime(timezone=True),
    )


class Product(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_PRODUITS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_PRODUITS"

    produit_code: Mapped[str] = mapped_column(
        "PRODUIT_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    produit_denomination: Mapped[str] = mapped_column(
        "PRODUIT_DENOMINATION",
        String(100),
        nullable=False,
    )
    produit_description: Mapped[str | None] = mapped_column("PRODUIT_DESCRIPTION", String(300))
    produit_logo: Mapped[str | None] = mapped_column("PRODUIT_LOGO", String(100))
    pays_code: Mapped[str] = mapped_column("PAYS_CODE", String(3), nullable=False)
    produit_date_debut: Mapped[datetime] = mapped_column(
        "PRODUIT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    produit_date_fin: Mapped[datetime | None] = mapped_column(
        "PRODUIT_DATE_FIN",
        DateTime(timezone=True),
    )
    produit_statut: Mapped[int | None] = mapped_column("PRODUIT_STATUT", SmallInteger)


class ProductRegime(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_PRODUITS_REGIMES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_PRODUITS_REGIMES"

    produit_code: Mapped[str] = mapped_column(
        "PRODUIT_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    regime_code: Mapped[str] = mapped_column(
        "REGIME_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    produit_regime_statut: Mapped[int] = mapped_column(
        "PRODUIT_REGIME_STATUT",
        SmallInteger,
        nullable=False,
    )
    produit_regime_date_debut: Mapped[datetime] = mapped_column(
        "PRODUIT_REGIME_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    produit_regime_date_fin: Mapped[datetime | None] = mapped_column(
        "PRODUIT_REGIME_DATE_FIN",
        DateTime(timezone=True),
    )


class CareBasket(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_PANIERS_SOINS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_PANIERS_SOINS"

    produit_code: Mapped[str] = mapped_column("PRODUIT_CODE", String(10), nullable=False)
    panier_code: Mapped[str] = mapped_column(
        "PANIER_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    panier_denomination: Mapped[str] = mapped_column(
        "PANIER_DENOMINATION",
        String(100),
        nullable=False,
    )
    panier_statut: Mapped[int] = mapped_column("PANIER_STATUT", SmallInteger, nullable=False)
    panier_date_debut: Mapped[datetime] = mapped_column(
        "PANIER_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    panier_date_fin: Mapped[datetime | None] = mapped_column(
        "PANIER_DATE_FIN",
        DateTime(timezone=True),
    )


class CareNetwork(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_RESEAUX_SOINS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_RESEAUX_SOINS"

    produit_code: Mapped[str] = mapped_column("PRODUIT_CODE", String(10), nullable=False)
    panier_code: Mapped[str] = mapped_column("PANIER_CODE", String(10), nullable=False)
    reseau_code: Mapped[str] = mapped_column(
        "RESEAU_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    reseau_denomination: Mapped[str] = mapped_column(
        "RESEAU_DENOMINATION",
        String(100),
        nullable=False,
    )
    reseau_observations: Mapped[str | None] = mapped_column("RESEAU_OBSERVATIONS", String(300))
    reseau_statut: Mapped[int] = mapped_column("RESEAU_STATUT", SmallInteger, nullable=False)
    reseau_date_debut: Mapped[datetime] = mapped_column(
        "RESEAU_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    reseau_date_fin: Mapped[datetime | None] = mapped_column(
        "RESEAU_DATE_FIN",
        DateTime(timezone=True),
    )


class NetworkMedicalAct(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_RESEAUX_SOINS_ACTES_MEDICAUX, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_RESEAUX_SOINS_ACTES_MEDICAUX"
    # Mirka ne declare pas de cle primaire sur cette table. Cette
    # identite ne vaut que pour l'ORM : rien n'est ajoute en base.
    __mapper_args__ = {"primary_key": ["reseau_code", "acte_medical_code", "reseau_acte_medical_date_debut"]}

    reseau_code: Mapped[str] = mapped_column(
        "RESEAU_CODE",
        String(10),
        primary_key=True,
        autoincrement=False,
    )
    acte_medical_code: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_CODE",
        String(7),
        primary_key=True,
        autoincrement=False,
    )
    reseau_acte_medical_base_remboursement: Mapped[int] = mapped_column(
        "RESEAU_ACTE_MEDICAL_BASE_REMBOURSEMENT",
        BigInteger,
        nullable=False,
    )
    reseau_acte_medical_plafond_remboursement: Mapped[int | None] = mapped_column(
        "RESEAU_ACTE_MEDICAL_PLAFOND_REMBOURSEMENT",
        BigInteger,
    )
    reseau_acte_medical_duree_plafond: Mapped[int | None] = mapped_column(
        "RESEAU_ACTE_MEDICAL_DUREE_PLAFOND",
        BigInteger,
    )
    reseau_acte_medical_statut_entente_prealable: Mapped[int] = mapped_column(
        "RESEAU_ACTE_MEDICAL_STATUT_ENTENTE_PREALABLE",
        SmallInteger,
        nullable=False,
    )
    reseau_acte_medical_delai_entente_prealable: Mapped[int | None] = mapped_column(
        "RESEAU_ACTE_MEDICAL_DELAI_ENTENTE_PREALABLE",
        SmallInteger,
    )
    reseau_acte_medical_statut: Mapped[int] = mapped_column(
        "RESEAU_ACTE_MEDICAL_STATUT",
        SmallInteger,
        nullable=False,
    )
    reseau_acte_medical_date_debut: Mapped[datetime] = mapped_column(
        "RESEAU_ACTE_MEDICAL_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    reseau_acte_medical_date_fin: Mapped[datetime | None] = mapped_column(
        "RESEAU_ACTE_MEDICAL_DATE_FIN",
        DateTime(timezone=True),
    )
    reseau_acte_medical_plafond_type: Mapped[str | None] = mapped_column(
        "RESEAU_ACTE_MEDICAL_PLAFOND_TYPE",
        String(100),
    )
    reseau_acte_medical_quantite_maximum: Mapped[Decimal | None] = mapped_column(
        "RESEAU_ACTE_MEDICAL_QUANTITE_MAXIMUM",
        Numeric,
    )


class InvoiceHealthProfessional(SimulationScopedMixin, AuditMixin, Base):
    """Table de faits Mirka TB_FACTURES_PROFESSIONNELS_SANTE, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_FACTURES_PROFESSIONNELS_SANTE"

    facture_numero: Mapped[Decimal] = mapped_column(
        "FACTURE_NUMERO",
        Numeric(38, 0),
        primary_key=True,
        autoincrement=False,
    )
    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        String(9),
        primary_key=True,
        autoincrement=False,
    )
    specialite_medicale_code: Mapped[str | None] = mapped_column(
        "SPECIALITE_MEDICALE_CODE",
        String(2),
    )
    professionnel_sante_date_debut: Mapped[datetime] = mapped_column(
        "PROFESSIONNEL_SANTE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    professionnel_sante_date_fin: Mapped[datetime | None] = mapped_column(
        "PROFESSIONNEL_SANTE_DATE_FIN",
        DateTime(timezone=True),
    )


class Country(AuditMixin, Base):
    """Référentiel Mirka TB_TV_LOCALISATION_PAYS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_LOCALISATION_PAYS"

    continent_code: Mapped[str] = mapped_column(
        "CONTINENT_CODE",
        String(2),
        primary_key=True,
        autoincrement=False,
    )
    pays_code: Mapped[str] = mapped_column(
        "PAYS_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    pays_code_numerique: Mapped[Decimal] = mapped_column(
        "PAYS_CODE_NUMERIQUE",
        Numeric(38, 0),
        nullable=False,
    )
    pays_denomination: Mapped[str] = mapped_column("PAYS_DENOMINATION", String(100), nullable=False)
    pays_gentile: Mapped[str] = mapped_column("PAYS_GENTILE", String(100), nullable=False)
    pays_indicatif: Mapped[Decimal] = mapped_column(
        "PAYS_INDICATIF",
        Numeric(38, 0),
        nullable=False,
    )
    pays_drapeau: Mapped[str | None] = mapped_column("PAYS_DRAPEAU", String(100))
    devise_code: Mapped[str] = mapped_column("DEVISE_CODE", String(3), nullable=False)
    pays_date_debut: Mapped[datetime] = mapped_column(
        "PAYS_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    pays_date_fin: Mapped[datetime | None] = mapped_column("PAYS_DATE_FIN", DateTime(timezone=True))
    pays_statut: Mapped[Decimal | None] = mapped_column("PAYS_STATUT", Numeric)
    pays_latitude: Mapped[str | None] = mapped_column("PAYS_LATITUDE", String(100))
    pays_longitude: Mapped[str | None] = mapped_column("PAYS_LONGITUDE", String(100))


class Region(AuditMixin, Base):
    """Référentiel Mirka TB_TV_LOCALISATION_REGIONS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_LOCALISATION_REGIONS"

    pays_code: Mapped[str] = mapped_column(
        "PAYS_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    region_type: Mapped[str] = mapped_column(
        "REGION_TYPE",
        String(1),
        primary_key=True,
        autoincrement=False,
    )
    region_code: Mapped[str] = mapped_column(
        "REGION_CODE",
        String(6),
        primary_key=True,
        autoincrement=False,
    )
    region_denomination: Mapped[str] = mapped_column(
        "REGION_DENOMINATION",
        String(100),
        nullable=False,
    )
    region_date_debut: Mapped[datetime] = mapped_column(
        "REGION_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    region_date_fin: Mapped[datetime | None] = mapped_column(
        "REGION_DATE_FIN",
        DateTime(timezone=True),
    )
    region_statut: Mapped[int | None] = mapped_column("REGION_STATUT", SmallInteger)
    region_latitude: Mapped[str | None] = mapped_column("REGION_LATITUDE", String(100))
    region_longitude: Mapped[str | None] = mapped_column("REGION_LONGITUDE", String(100))


class Department(AuditMixin, Base):
    """Référentiel Mirka TB_TV_LOCALISATION_DEPARTEMENTS, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_LOCALISATION_DEPARTEMENTS"

    region_code: Mapped[str] = mapped_column(
        "REGION_CODE",
        String(6),
        primary_key=True,
        autoincrement=False,
    )
    departement_type: Mapped[str] = mapped_column(
        "DEPARTEMENT_TYPE",
        String(1),
        primary_key=True,
        autoincrement=False,
    )
    departement_code: Mapped[str] = mapped_column(
        "DEPARTEMENT_CODE",
        String(7),
        primary_key=True,
        autoincrement=False,
    )
    departement_denomination: Mapped[str] = mapped_column(
        "DEPARTEMENT_DENOMINATION",
        String(100),
        nullable=False,
    )
    departement_date_debut: Mapped[datetime] = mapped_column(
        "DEPARTEMENT_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    departement_date_fin: Mapped[datetime | None] = mapped_column(
        "DEPARTEMENT_DATE_FIN",
        DateTime(timezone=True),
    )
    departement_statut: Mapped[int | None] = mapped_column("DEPARTEMENT_STATUT", SmallInteger)
    departement_latitude: Mapped[str | None] = mapped_column("DEPARTEMENT_LATITUDE", String(100))
    departement_longitude: Mapped[str | None] = mapped_column("DEPARTEMENT_LONGITUDE", String(100))


class Locality(AuditMixin, Base):
    """Référentiel Mirka TB_TV_LOCALISATION_LOCALITES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_LOCALISATION_LOCALITES"

    departement_code: Mapped[str] = mapped_column(
        "DEPARTEMENT_CODE",
        String(7),
        primary_key=True,
        autoincrement=False,
    )
    localite_type: Mapped[str] = mapped_column(
        "LOCALITE_TYPE",
        String(1),
        primary_key=True,
        autoincrement=False,
    )
    localite_code: Mapped[str] = mapped_column(
        "LOCALITE_CODE",
        String(8),
        primary_key=True,
        autoincrement=False,
    )
    localite_denomination: Mapped[str] = mapped_column(
        "LOCALITE_DENOMINATION",
        String(100),
        nullable=False,
    )
    localite_date_debut: Mapped[datetime] = mapped_column(
        "LOCALITE_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    localite_date_fin: Mapped[datetime | None] = mapped_column(
        "LOCALITE_DATE_FIN",
        DateTime(timezone=True),
    )
    localite_statut: Mapped[int | None] = mapped_column("LOCALITE_STATUT", SmallInteger)
    localite_latitude: Mapped[str | None] = mapped_column("LOCALITE_LATITUDE", String(100))
    localite_longitude: Mapped[str | None] = mapped_column("LOCALITE_LONGITUDE", String(100))


class Regime(AuditMixin, Base):
    """Référentiel Mirka TB_TV_REGIMES, transposé pour le simulateur."""

    __tablename__ = "TB_SIM_TV_REGIMES"

    regime_code: Mapped[str] = mapped_column(
        "REGIME_CODE",
        String(3),
        primary_key=True,
        autoincrement=False,
    )
    regime_code_parent: Mapped[str | None] = mapped_column("REGIME_CODE_PARENT", String(3))
    regime_denomination: Mapped[str] = mapped_column(
        "REGIME_DENOMINATION",
        String(100),
        nullable=False,
    )
    regime_taux: Mapped[int] = mapped_column("REGIME_TAUX", SmallInteger, nullable=False)
    regime_date_debut: Mapped[datetime] = mapped_column(
        "REGIME_DATE_DEBUT",
        DateTime(timezone=True),
        primary_key=True,
        autoincrement=False,
        server_default=func.now(),
    )
    regime_date_fin: Mapped[datetime | None] = mapped_column(
        "REGIME_DATE_FIN",
        DateTime(timezone=True),
    )
    regime_statut: Mapped[int | None] = mapped_column("REGIME_STATUT", SmallInteger)
