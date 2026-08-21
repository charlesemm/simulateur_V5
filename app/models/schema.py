"""Décrit toutes les tables TB_XXX et leurs relations explicites."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class InsuredPerson(AuditMixin, Base):
    """Représente un assuré du référentiel CMU."""

    __tablename__ = "TB_REF_ASSURES"

    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID", PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    numero_recepisse: Mapped[str | None] = mapped_column("NUMERO_RECEPISSE", String(50))
    assure_numero_identifiant: Mapped[str | None] = mapped_column(
        "ASSURE_NUMERO_IDENTIFIANT", String(50)
    )
    numero_secu: Mapped[str] = mapped_column(
        "NUMERO_SECU", String(50), nullable=False, unique=True
    )
    civilite_code: Mapped[str | None] = mapped_column("CIVILITE_CODE", String(10))
    assure_nom: Mapped[str] = mapped_column("ASSURE_NOM", String(150), nullable=False)
    assure_nom_patronymique: Mapped[str | None] = mapped_column(
        "ASSURE_NOM_PATRONYMIQUE", String(150)
    )
    assure_prenoms: Mapped[str | None] = mapped_column(
        "ASSURE_PRENOMS", String(150)
    )
    assure_date_naissance: Mapped[date | None] = mapped_column(
        "ASSURE_DATE_NAISSANCE", Date
    )
    regime_code: Mapped[str | None] = mapped_column("REGIME_CODE", String(10))

    invoices: Mapped[list[Invoice]] = relationship(back_populates="insured_person")
    prior_authorizations: Mapped[list[PriorAuthorization]] = relationship(
        back_populates="insured_person"
    )
    identifiers: Mapped[list["InsuredIdentifier"]] = relationship(
        back_populates="insured_person"
    )
    professions: Mapped[list["InsuredProfession"]] = relationship(
        back_populates="insured_person"
    )
    birth_info: Mapped[list["InsuredBirthInfo"]] = relationship(
        back_populates="insured_person"
    )
    rights: Mapped[list["InsuredRight"]] = relationship(back_populates="insured_person")


class HealthCenter(AuditMixin, Base):
    """Décrit un centre de santé agréé par la CMU."""

    __tablename__ = "TB_REF_CENTRES_SANTE"

    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE", String(30), primary_key=True
    )
    collectivite_code: Mapped[str | None] = mapped_column("COLLECTIVITE_CODE", String(30))
    type_etablissement_sanitaire_code: Mapped[str | None] = mapped_column(
        "TYPE_ETABLISSEMENT_SANITAIRE_CODE", String(30)
    )
    centre_sante_numero_immatriculation: Mapped[str] = mapped_column(
        "CENTRE_SANTE_NUMERO_IMMATRICULATION", String(50), nullable=False, unique=True
    )
    centre_sante_denomination: Mapped[str] = mapped_column(
        "CENTRE_SANTE_DENOMINATION", String(255), nullable=False
    )

    agent_assignments: Mapped[list[CenterHealthAgent]] = relationship(
        back_populates="health_center", cascade="all, delete-orphan"
    )
    professional_assignments: Mapped[list[HealthProfessionalCenter]] = relationship(
        back_populates="health_center", cascade="all, delete-orphan"
    )
    invoices: Mapped[list[Invoice]] = relationship(back_populates="health_center")
    prior_authorizations: Mapped[list[PriorAuthorization]] = relationship(
        back_populates="health_center"
    )


class Agent(AuditMixin, Base):
    """Représente un agent CMU et son rôle opérationnel."""

    __tablename__ = "TB_REF_AGENTS"
    __table_args__ = (
        CheckConstraint(
            '"AGENT_TYPE_CODE" IN (\'accueil\', \'medecin_conseil\', \'autre\')',
            name="CK_TB_REF_AGENTS_TYPE",
        ),
    )

    # Une validation automatique n'est attribuée à aucun médecin conseil.
    agent_code: Mapped[str] = mapped_column(
        "AGENT_CODE", String(30), primary_key=True
    )
    agent_code_gestion: Mapped[str | None] = mapped_column("AGENT_CODE_GESTION", String(30))
    agent_prenoms: Mapped[str] = mapped_column("AGENT_PRENOMS", String(150), nullable=False)
    agent_nom: Mapped[str] = mapped_column("AGENT_NOM", String(150), nullable=False)
    agent_email: Mapped[str] = mapped_column(
        "AGENT_EMAIL", String(255), nullable=False, unique=True
    )
    agent_type_code: Mapped[str] = mapped_column(
        "AGENT_TYPE_CODE", String(30), nullable=False
    )

    center_assignments: Mapped[list[CenterHealthAgent]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    prior_authorization_statuses: Mapped[list[PriorAuthorizationStatus]] = relationship(
        back_populates="agent"
    )


class CenterHealthAgent(AuditMixin, Base):
    """Historise l'affectation d'un agent à un centre de santé."""

    __tablename__ = "TB_CENTRES_SANTE_AGENTS"

    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        ForeignKey("TB_REF_CENTRES_SANTE.CENTRE_SANTE_CODE"),
        primary_key=True,
    )
    agent_code: Mapped[str] = mapped_column(
        "AGENT_CODE", ForeignKey("TB_REF_AGENTS.AGENT_CODE"), primary_key=True
    )
    date_debut: Mapped[date] = mapped_column("DATE_DEBUT", Date, primary_key=True)
    date_fin: Mapped[date | None] = mapped_column("DATE_FIN", Date)

    health_center: Mapped[HealthCenter] = relationship(back_populates="agent_assignments")
    agent: Mapped[Agent] = relationship(back_populates="center_assignments")


class HealthProfessional(AuditMixin, Base):
    """Décrit un professionnel intervenant dans le parcours de soins."""

    __tablename__ = "TB_REF_PROFESSIONNELS_SANTE"

    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE", String(30), primary_key=True
    )
    nom: Mapped[str] = mapped_column("NOM", String(150), nullable=False)
    prenoms: Mapped[str] = mapped_column("PRENOMS", String(150), nullable=False)
    type_code: Mapped[str] = mapped_column("TYPE_CODE", String(30), nullable=False)
    numero_ordre: Mapped[str | None] = mapped_column("NUMERO_ORDRE", String(50))
    statut: Mapped[str] = mapped_column("STATUT", String(30), nullable=False)

    specialty_assignments: Mapped[list[HealthProfessionalMedicalSpecialty]] = relationship(
        back_populates="health_professional", cascade="all, delete-orphan"
    )
    center_assignments: Mapped[list[HealthProfessionalCenter]] = relationship(
        back_populates="health_professional", cascade="all, delete-orphan"
    )
    invoice_provisions: Mapped[list[InvoiceProvision]] = relationship(
        back_populates="health_professional"
    )
    prior_authorization_medical_acts: Mapped[list[PriorAuthorizationMedicalAct]] = relationship(
        back_populates="health_professional"
    )
    prior_authorization_provisions: Mapped[list[PriorAuthorizationProvision]] = relationship(
        back_populates="health_professional"
    )


class MedicalSpecialty(AuditMixin, Base):
    """Référence une spécialité médicale reconnue."""

    __tablename__ = "TB_REF_SPECIALITES_MEDICALES"

    specialite_medicale_code: Mapped[str] = mapped_column(
        "SPECIALITE_MEDICALE_CODE", String(30), primary_key=True
    )
    denomination: Mapped[str] = mapped_column("DENOMINATION", String(255), nullable=False)

    professional_assignments: Mapped[list[HealthProfessionalMedicalSpecialty]] = relationship(
        back_populates="medical_specialty", cascade="all, delete-orphan"
    )


class HealthProfessionalMedicalSpecialty(AuditMixin, Base):
    """Historise les spécialités d'un professionnel de santé."""

    __tablename__ = "TB_REF_PROFESSIONNELS_SANTE_SPECIALITES_MEDICALES"

    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        ForeignKey("TB_REF_PROFESSIONNELS_SANTE.PROFESSIONNEL_SANTE_CODE"),
        primary_key=True,
    )
    specialite_medicale_code: Mapped[str] = mapped_column(
        "SPECIALITE_MEDICALE_CODE",
        ForeignKey("TB_REF_SPECIALITES_MEDICALES.SPECIALITE_MEDICALE_CODE"),
        primary_key=True,
    )
    date_debut: Mapped[date] = mapped_column("DATE_DEBUT", Date, primary_key=True)
    date_fin: Mapped[date | None] = mapped_column("DATE_FIN", Date)

    health_professional: Mapped[HealthProfessional] = relationship(
        back_populates="specialty_assignments"
    )
    medical_specialty: Mapped[MedicalSpecialty] = relationship(
        back_populates="professional_assignments"
    )


class HealthProfessionalCenter(AuditMixin, Base):
    """Historise l'exercice d'un professionnel dans un centre."""

    __tablename__ = "TB_PROFESSIONNELS_SANTE_CENTRES_SANTE"

    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        ForeignKey("TB_REF_PROFESSIONNELS_SANTE.PROFESSIONNEL_SANTE_CODE"),
        primary_key=True,
    )
    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        ForeignKey("TB_REF_CENTRES_SANTE.CENTRE_SANTE_CODE"),
        primary_key=True,
    )
    date_debut: Mapped[date] = mapped_column("DATE_DEBUT", Date, primary_key=True)
    date_fin: Mapped[date | None] = mapped_column("DATE_FIN", Date)

    health_professional: Mapped[HealthProfessional] = relationship(
        back_populates="center_assignments"
    )
    health_center: Mapped[HealthCenter] = relationship(
        back_populates="professional_assignments"
    )


class Pathology(AuditMixin, Base):
    """Référence une version datée d'une pathologie interne."""

    __tablename__ = "TB_REF_PATHOLOGIES"

    pathologie_code: Mapped[str] = mapped_column(
        "PATHOLOGIE_CODE", String(3), primary_key=True
    )
    pathologie_date_debut: Mapped[date] = mapped_column(
        "PATHOLOGIE_DATE_DEBUT", Date, primary_key=True
    )
    sous_chapitre_code: Mapped[str | None] = mapped_column("SOUS_CHAPITRE_CODE", String(30))
    pathologie_denomination: Mapped[str] = mapped_column(
        "PATHOLOGIE_DENOMINATION", String(255), nullable=False
    )
    pathologie_date_fin: Mapped[date | None] = mapped_column("PATHOLOGIE_DATE_FIN", Date)
    pathologie_statut: Mapped[str] = mapped_column(
        "PATHOLOGIE_STATUT", String(30), nullable=False
    )

    invoice_pathologies: Mapped[list[InvoicePathology]] = relationship(
        back_populates="pathology"
    )


class Medication(AuditMixin, Base):
    """Référence une version datée d'un médicament."""

    __tablename__ = "TB_REF_MEDICAMENTS"

    medicament_code: Mapped[str] = mapped_column(
        "MEDICAMENT_CODE", String(30), primary_key=True
    )
    medicament_date_debut: Mapped[date] = mapped_column(
        "MEDICAMENT_DATE_DEBUT", Date, primary_key=True
    )
    type_code: Mapped[str | None] = mapped_column("TYPE_CODE", String(30))
    medicament_denomination: Mapped[str] = mapped_column(
        "MEDICAMENT_DENOMINATION", String(255), nullable=False
    )
    medicament_ean13: Mapped[str | None] = mapped_column("MEDICAMENT_EAN13", String(13))
    dci_code: Mapped[str | None] = mapped_column("DCI_CODE", String(30))
    laboratoire_code: Mapped[str | None] = mapped_column("LABORATOIRE_CODE", String(30))
    famille_forme_code: Mapped[str | None] = mapped_column("FAMILLE_FORME_CODE", String(30))
    conditionnement_code: Mapped[str | None] = mapped_column("CONDITIONNEMENT_CODE", String(30))
    presentation_code: Mapped[str | None] = mapped_column("PRESENTATION_CODE", String(30))
    liste_types_factures: Mapped[str | None] = mapped_column("LISTE_TYPES_FACTURES", Text)
    liste_genres: Mapped[str | None] = mapped_column("LISTE_GENRES", Text)
    medicament_quantite_maximum: Mapped[int | None] = mapped_column(
        "MEDICAMENT_QUANTITE_MAXIMUM", Integer
    )
    medicament_age_minimum: Mapped[int | None] = mapped_column(
        "MEDICAMENT_AGE_MINIMUM", Integer
    )
    medicament_age_maximum: Mapped[int | None] = mapped_column(
        "MEDICAMENT_AGE_MAXIMUM", Integer
    )
    medicament_hapax_statut: Mapped[bool] = mapped_column(
        "MEDICAMENT_HAPAX_STATUT", Boolean, nullable=False, default=False
    )
    medicament_tarif_default: Mapped[Decimal] = mapped_column(
        "MEDICAMENT_TARIF_DEFAULT", Numeric(15, 2), nullable=False
    )
    medicament_statut: Mapped[str] = mapped_column(
        "MEDICAMENT_STATUT", String(30), nullable=False
    )
    medicament_date_fin: Mapped[date | None] = mapped_column("MEDICAMENT_DATE_FIN", Date)


class MedicalAct(AuditMixin, Base):
    """Référence une version datée d'un acte médical."""

    __tablename__ = "TB_REF_ACTES_MEDICAUX"

    acte_medical_code: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_CODE", String(30), primary_key=True
    )
    acte_medical_date_debut: Mapped[date] = mapped_column(
        "ACTE_MEDICAL_DATE_DEBUT", Date, primary_key=True
    )
    article_code: Mapped[str | None] = mapped_column("ARTICLE_CODE", String(30))
    acte_medical_type: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_TYPE", String(30), nullable=False
    )
    acte_medical_denomination: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_DENOMINATION", String(255), nullable=False
    )
    liste_types_factures: Mapped[str | None] = mapped_column("LISTE_TYPES_FACTURES", Text)
    liste_genres: Mapped[str | None] = mapped_column("LISTE_GENRES", Text)
    acte_medical_age_minimum: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_AGE_MINIMUM", Integer
    )
    acte_medical_age_maximum: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_AGE_MAXIMUM", Integer
    )
    acte_medical_quantite_maximum: Mapped[int | None] = mapped_column(
        "ACTE_MEDICAL_QUANTITE_MAXIMUM", Integer
    )
    acte_medical_hapax_statut: Mapped[bool] = mapped_column(
        "ACTE_MEDICAL_HAPAX_STATUT", Boolean, nullable=False, default=False
    )
    acte_medical_statut: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_STATUT", String(30), nullable=False
    )
    acte_medical_date_fin: Mapped[date | None] = mapped_column(
        "ACTE_MEDICAL_DATE_FIN", Date
    )


class TypeInvoice(AuditMixin, Base):
    """Référence une version datée d'un type de facture."""

    __tablename__ = "TB_TV_TYPES_FACTURES"

    type_facture_code: Mapped[str] = mapped_column(
        "TYPE_FACTURE_CODE", String(30), primary_key=True
    )
    type_facture_date_debut: Mapped[date] = mapped_column(
        "TYPE_FACTURE_DATE_DEBUT", Date, primary_key=True
    )
    type_facture_denomination: Mapped[str] = mapped_column(
        "TYPE_FACTURE_DENOMINATION", String(255), nullable=False
    )
    type_facture_date_fin: Mapped[date | None] = mapped_column(
        "TYPE_FACTURE_DATE_FIN", Date
    )
    type_facture_statut: Mapped[str] = mapped_column(
        "TYPE_FACTURE_STATUT", String(30), nullable=False
    )


class Invoice(AuditMixin, Base):
    """Porte la facture centrale d'un parcours de soins."""

    __tablename__ = "TB_FACTURES"
    __table_args__ = (
        # Seuls RAM et RGB existent dans TB_TV_REGIMES : « CMU » nomme le
        # dispositif, pas un régime.
        CheckConstraint(
            "\"REGIME_CODE\" IS NULL OR \"REGIME_CODE\" IN ('RAM', 'RGB')",
            name="ck_factures_regime_valide",
        ),
    )

    facture_numero: Mapped[str] = mapped_column(
        "FACTURE_NUMERO", String(50), primary_key=True
    )
    produit_code: Mapped[str | None] = mapped_column("PRODUIT_CODE", String(30))
    regime_code: Mapped[str | None] = mapped_column("REGIME_CODE", String(30))
    regime_taux: Mapped[Decimal | None] = mapped_column("REGIME_TAUX", Numeric(5, 2))
    organisme_code: Mapped[str | None] = mapped_column("ORGANISME_CODE", String(30))
    assurance_code: Mapped[str | None] = mapped_column("ASSURANCE_CODE", String(30))
    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID", ForeignKey("TB_REF_ASSURES.PERSONNE_UUID"), nullable=False
    )
    type_facture_code: Mapped[str] = mapped_column(
        "TYPE_FACTURE_CODE", String(30), nullable=False
    )
    facture_date_soins: Mapped[date] = mapped_column(
        "FACTURE_DATE_SOINS", Date, nullable=False
    )
    dossier_numero: Mapped[str | None] = mapped_column(
        "DOSSIER_NUMERO", String(50)
    )
    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        ForeignKey("TB_REF_CENTRES_SANTE.CENTRE_SANTE_CODE"),
        nullable=False,
    )
    centre_sante_type_code: Mapped[str | None] = mapped_column(
        "CENTRE_SANTE_TYPE_CODE", String(30)
    )
    centre_sante_type_libelle: Mapped[str | None] = mapped_column(
        "CENTRE_SANTE_TYPE_LIBELLE", String(255)
    )
    reseau_code: Mapped[str | None] = mapped_column("RESEAU_CODE", String(30))
    # use_alter résout le cycle physique entre facture et entente préalable.
    entente_prealable_id: Mapped[int | None] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        ForeignKey(
            "TB_ENTENTES_PREALABLES.ENTENTE_PREALABLE_ID",
            name="FK_FACTURE_ENTENTE",
            use_alter=True,
        ),
    )

    insured_person: Mapped[InsuredPerson] = relationship(back_populates="invoices")
    health_center: Mapped[HealthCenter] = relationship(back_populates="invoices")
    prior_authorization: Mapped[PriorAuthorization | None] = relationship(
        foreign_keys=[entente_prealable_id], back_populates="linked_invoices"
    )
    linked_prior_authorizations: Mapped[list[PriorAuthorization]] = relationship(
        foreign_keys="PriorAuthorization.facture_numero", back_populates="invoice"
    )
    pathologies: Mapped[list[InvoicePathology]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    prescriptions: Mapped[list[InvoicePrescription]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    provisions: Mapped[list[InvoiceProvision]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    rejections: Mapped[list[InvoiceRejection]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    statuses: Mapped[list[InvoiceStatus]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoicePathology(AuditMixin, Base):
    """Associe une facture à une version précise de pathologie."""

    __tablename__ = "TB_FACTURES_PATHOLOGIES"
    __table_args__ = (
        ForeignKeyConstraint(
            ["PATHOLOGIE_CODE", "PATHOLOGIE_DATE_DEBUT"],
            [
                "TB_REF_PATHOLOGIES.PATHOLOGIE_CODE",
                "TB_REF_PATHOLOGIES.PATHOLOGIE_DATE_DEBUT",
            ],
            name="FK_FACTURE_PATHOLOGIE_REF",
        ),
    )

    facture_numero: Mapped[str] = mapped_column(
        "FACTURE_NUMERO", ForeignKey("TB_FACTURES.FACTURE_NUMERO"), primary_key=True
    )
    pathologie_code: Mapped[str] = mapped_column(
        "PATHOLOGIE_CODE", String(3), primary_key=True
    )
    pathologie_date_debut: Mapped[date] = mapped_column(
        "PATHOLOGIE_DATE_DEBUT", Date, primary_key=True
    )
    pathologie_observations: Mapped[str | None] = mapped_column(
        "PATHOLOGIE_OBSERVATIONS", Text
    )
    pathologie_date_fin: Mapped[date | None] = mapped_column(
        "PATHOLOGIE_DATE_FIN", Date
    )

    invoice: Mapped[Invoice] = relationship(back_populates="pathologies")
    pathology: Mapped[Pathology] = relationship(back_populates="invoice_pathologies")


class InvoicePrescription(AuditMixin, Base):
    """Enregistre une prescription liée à une facture."""

    __tablename__ = "TB_FACTURES_PRESCRIPTIONS"

    facture_numero: Mapped[str] = mapped_column(
        "FACTURE_NUMERO", ForeignKey("TB_FACTURES.FACTURE_NUMERO"), primary_key=True
    )
    prescription_code: Mapped[str] = mapped_column(
        "PRESCRIPTION_CODE", String(30), primary_key=True
    )
    date_debut: Mapped[date] = mapped_column("DATE_DEBUT", Date, primary_key=True)
    prescription_quantite: Mapped[Decimal | None] = mapped_column(
        "PRESCRIPTION_QUANTITE", Numeric(10, 2)
    )
    prescription_posologie: Mapped[str | None] = mapped_column(
        "PRESCRIPTION_POSOLOGIE", Text
    )
    prescription_duree: Mapped[int | None] = mapped_column("PRESCRIPTION_DUREE", Integer)
    prescription_renseignements_cliniques: Mapped[str | None] = mapped_column(
        "PRESCRIPTION_RENSEIGNEMENTS_CLINIQUES", Text
    )
    date_fin: Mapped[date | None] = mapped_column("DATE_FIN", Date)

    invoice: Mapped[Invoice] = relationship(back_populates="prescriptions")


class InvoiceProvision(AuditMixin, Base):
    """Détaille une prestation et son calcul de remboursement."""

    __tablename__ = "TB_FACTURES_PRESTATIONS"

    facture_numero: Mapped[str] = mapped_column(
        "FACTURE_NUMERO", ForeignKey("TB_FACTURES.FACTURE_NUMERO"), primary_key=True
    )
    prestation_code: Mapped[str] = mapped_column(
        "PRESTATION_CODE", String(30), primary_key=True
    )
    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        ForeignKey("TB_REF_PROFESSIONNELS_SANTE.PROFESSIONNEL_SANTE_CODE"),
        nullable=False,
    )
    statut_remboursement: Mapped[str | None] = mapped_column(
        "STATUT_REMBOURSEMENT", String(30)
    )
    motif_non_remboursement: Mapped[str | None] = mapped_column(
        "MOTIF_NON_REMBOURSEMENT", Text
    )
    prestation_base_remboursement: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_BASE_REMBOURSEMENT", Numeric(15, 2)
    )
    prestation_taux_remboursement: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_TAUX_REMBOURSEMENT", Numeric(5, 2)
    )
    prestation_quantite_prescrite: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_QUANTITE_PRESCRITE", Numeric(10, 2)
    )
    prestation_quantite_servie: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_QUANTITE_SERVIE", Numeric(10, 2)
    )
    prestation_prix_unitaire: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_PRIX_UNITAIRE", Numeric(15, 2)
    )
    prestation_montant_depense: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_DEPENSE", Numeric(15, 2)
    )
    prestation_montant_rq: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_RQ", Numeric(15, 2)
    )
    prestation_montant_complementaire: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_COMPLEMENTAIRE", Numeric(15, 2)
    )
    prestation_montant_remise: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_REMISE", Numeric(15, 2)
    )
    prestation_montant_assure: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_MONTANT_ASSURE", Numeric(15, 2)
    )
    prestation_date_debut: Mapped[date | None] = mapped_column(
        "PRESTATION_DATE_DEBUT", Date
    )
    prestation_date_fin: Mapped[date | None] = mapped_column("PRESTATION_DATE_FIN", Date)
    dents_numeros: Mapped[str | None] = mapped_column("DENTS_NUMEROS", String(100))
    statut_code: Mapped[str | None] = mapped_column("STATUT_CODE", String(30))
    motif_rejet_code: Mapped[str | None] = mapped_column("MOTIF_REJET_CODE", String(30))
    prestation_observations: Mapped[str | None] = mapped_column(
        "PRESTATION_OBSERVATIONS", Text
    )

    invoice: Mapped[Invoice] = relationship(back_populates="provisions")
    health_professional: Mapped[HealthProfessional] = relationship(
        back_populates="invoice_provisions"
    )


class InvoiceRejection(AuditMixin, Base):
    """Historise les rejets appliqués à une facture."""

    __tablename__ = "TB_FACTURES_REJETS"

    facture_numero: Mapped[str] = mapped_column(
        "FACTURE_NUMERO", ForeignKey("TB_FACTURES.FACTURE_NUMERO"), primary_key=True
    )
    rejet_code: Mapped[str] = mapped_column("REJET_CODE", String(30), primary_key=True)
    rejet_date_debut: Mapped[date] = mapped_column(
        "REJET_DATE_DEBUT", Date, primary_key=True
    )
    rejet_date_fin: Mapped[date | None] = mapped_column("REJET_DATE_FIN", Date)

    invoice: Mapped[Invoice] = relationship(back_populates="rejections")


class InvoiceStatus(AuditMixin, Base):
    """Historise les changements de statut d'une facture."""

    __tablename__ = "TB_FACTURES_STATUTS"

    facture_numero: Mapped[str] = mapped_column(
        "FACTURE_NUMERO", ForeignKey("TB_FACTURES.FACTURE_NUMERO"), primary_key=True
    )
    statut_code: Mapped[str] = mapped_column("STATUT_CODE", String(30), primary_key=True)
    statut_date_debut: Mapped[date] = mapped_column(
        "STATUT_DATE_DEBUT", Date, primary_key=True
    )
    statut_observations: Mapped[str | None] = mapped_column("STATUT_OBSERVATIONS", Text)
    statut_date_fin: Mapped[date | None] = mapped_column("STATUT_DATE_FIN", Date)

    invoice: Mapped[Invoice] = relationship(back_populates="statuses")


class PriorAuthorization(AuditMixin, Base):
    """Porte une demande d'entente préalable."""

    __tablename__ = "TB_ENTENTES_PREALABLES"
    __table_args__ = (
        UniqueConstraint("ENTENTE_PREALABLE_NUMERO", name="UQ_ENTENTE_NUMERO"),
    )

    entente_prealable_id: Mapped[int] = mapped_column(
        "ENTENTE_PREALABLE_ID", Integer, primary_key=True, autoincrement=True
    )
    entente_prealable_numero: Mapped[str] = mapped_column(
        "ENTENTE_PREALABLE_NUMERO", String(50), nullable=False
    )
    centre_sante_code: Mapped[str] = mapped_column(
        "CENTRE_SANTE_CODE",
        ForeignKey("TB_REF_CENTRES_SANTE.CENTRE_SANTE_CODE"),
        nullable=False,
    )
    personne_uuid: Mapped[UUID] = mapped_column(
        "PERSONNE_UUID", ForeignKey("TB_REF_ASSURES.PERSONNE_UUID"), nullable=False
    )
    dossier_numero: Mapped[str | None] = mapped_column(
        "DOSSIER_NUMERO", String(50)
    )
    entente_prealable_date_debut: Mapped[date] = mapped_column(
        "ENTENTE_PREALABLE_DATE_DEBUT", Date, nullable=False
    )
    entente_prealable_date_fin: Mapped[date | None] = mapped_column(
        "ENTENTE_PREALABLE_DATE_FIN", Date
    )
    entente_prealable_numero_organisme: Mapped[str | None] = mapped_column(
        "ENTENTE_PREALABLE_NUMERO_ORGANISME", String(50)
    )
    organisme_code: Mapped[str | None] = mapped_column("ORGANISME_CODE", String(30))
    facture_numero: Mapped[str | None] = mapped_column(
        "FACTURE_NUMERO", ForeignKey("TB_FACTURES.FACTURE_NUMERO")
    )
    type_demande_code: Mapped[str] = mapped_column(
        "TYPE_DEMANDE_CODE", String(30), nullable=False
    )
    type_hospitalisation_code: Mapped[str | None] = mapped_column(
        "TYPE_HOSPITALISATION_CODE", String(30)
    )

    health_center: Mapped[HealthCenter] = relationship(
        back_populates="prior_authorizations"
    )
    insured_person: Mapped[InsuredPerson] = relationship(
        back_populates="prior_authorizations"
    )
    invoice: Mapped[Invoice | None] = relationship(
        foreign_keys=[facture_numero], back_populates="linked_prior_authorizations"
    )
    linked_invoices: Mapped[list[Invoice]] = relationship(
        foreign_keys="Invoice.entente_prealable_id", back_populates="prior_authorization"
    )
    statuses: Mapped[list[PriorAuthorizationStatus]] = relationship(
        back_populates="prior_authorization", cascade="all, delete-orphan"
    )
    medical_acts: Mapped[list[PriorAuthorizationMedicalAct]] = relationship(
        back_populates="prior_authorization", cascade="all, delete-orphan"
    )
    provisions: Mapped[list[PriorAuthorizationProvision]] = relationship(
        back_populates="prior_authorization", cascade="all, delete-orphan"
    )


class PriorAuthorizationStatus(AuditMixin, Base):
    """Historise le traitement d'une entente par un médecin conseil."""

    __tablename__ = "TB_ENTENTES_PREALABLES_STATUTS"

    entente_prealable_id: Mapped[int] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        ForeignKey("TB_ENTENTES_PREALABLES.ENTENTE_PREALABLE_ID"),
        primary_key=True,
    )
    statut_code: Mapped[str] = mapped_column("STATUT_CODE", String(30), primary_key=True)
    statut_date_debut: Mapped[date] = mapped_column(
        "STATUT_DATE_DEBUT", Date, primary_key=True
    )
    agent_code: Mapped[str] = mapped_column(
        "AGENT_CODE", ForeignKey("TB_REF_AGENTS.AGENT_CODE"), nullable=False
    )
    statut_date_fin: Mapped[date | None] = mapped_column("STATUT_DATE_FIN", Date)

    prior_authorization: Mapped[PriorAuthorization] = relationship(
        back_populates="statuses"
    )
    agent: Mapped[Agent] = relationship(back_populates="prior_authorization_statuses")


class PriorAuthorizationMedicalAct(AuditMixin, Base):
    """Détaille la décision d'entente pour un acte médical."""

    __tablename__ = "TB_ENTENTES_PREALABLES_ACTES_MEDICAUX"

    entente_prealable_id: Mapped[int] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        ForeignKey("TB_ENTENTES_PREALABLES.ENTENTE_PREALABLE_ID"),
        primary_key=True,
    )
    acte_medical_code: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_CODE", String(30), primary_key=True
    )
    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        ForeignKey("TB_REF_PROFESSIONNELS_SANTE.PROFESSIONNEL_SANTE_CODE"),
        nullable=False,
    )
    acte_medical_motif: Mapped[str | None] = mapped_column("ACTE_MEDICAL_MOTIF", Text)
    acte_medical_base_remboursement: Mapped[Decimal | None] = mapped_column(
        "ACTE_MEDICAL_BASE_REMBOURSEMENT", Numeric(15, 2)
    )
    acte_medical_taux_remboursement: Mapped[Decimal | None] = mapped_column(
        "ACTE_MEDICAL_TAUX_REMBOURSEMENT", Numeric(5, 2)
    )
    acte_medical_montant_cmu: Mapped[Decimal | None] = mapped_column(
        "ACTE_MEDICAL_MONTANT_CMU", Numeric(15, 2)
    )
    acte_medical_montant_assure: Mapped[Decimal | None] = mapped_column(
        "ACTE_MEDICAL_MONTANT_ASSURE", Numeric(15, 2)
    )
    acte_medical_statut: Mapped[str] = mapped_column(
        "ACTE_MEDICAL_STATUT", String(30), nullable=False
    )
    acte_medical_motif_rejet: Mapped[str | None] = mapped_column(
        "ACTE_MEDICAL_MOTIF_REJET", Text
    )

    prior_authorization: Mapped[PriorAuthorization] = relationship(
        back_populates="medical_acts"
    )
    health_professional: Mapped[HealthProfessional] = relationship(
        back_populates="prior_authorization_medical_acts"
    )


class PriorAuthorizationProvision(AuditMixin, Base):
    """Détaille la décision d'entente pour une prestation."""

    __tablename__ = "TB_ENTENTES_PREALABLES_PRESTATIONS"

    entente_prealable_id: Mapped[int] = mapped_column(
        "ENTENTE_PREALABLE_ID",
        ForeignKey("TB_ENTENTES_PREALABLES.ENTENTE_PREALABLE_ID"),
        primary_key=True,
    )
    prestation_code: Mapped[str] = mapped_column(
        "PRESTATION_CODE", String(30), primary_key=True
    )
    professionnel_sante_code: Mapped[str] = mapped_column(
        "PROFESSIONNEL_SANTE_CODE",
        ForeignKey("TB_REF_PROFESSIONNELS_SANTE.PROFESSIONNEL_SANTE_CODE"),
        nullable=False,
    )
    prestation_motif: Mapped[str | None] = mapped_column("PRESTATION_MOTIF", Text)
    prestation_prix_unitaire: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_PRIX_UNITAIRE", Numeric(15, 2)
    )
    prestation_quantite: Mapped[Decimal | None] = mapped_column(
        "PRESTATION_QUANTITE", Numeric(10, 2)
    )
    prestation_statut: Mapped[str] = mapped_column(
        "PRESTATION_STATUT", String(30), nullable=False
    )
    prestation_motif_rejet: Mapped[str | None] = mapped_column(
        "PRESTATION_MOTIF_REJET", Text
    )

    prior_authorization: Mapped[PriorAuthorization] = relationship(
        back_populates="provisions"
    )
    health_professional: Mapped[HealthProfessional] = relationship(
        back_populates="prior_authorization_provisions"
    )