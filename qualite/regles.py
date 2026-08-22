"""Les règles de qualité appliquées aux données produites par une exécution.

Quatre dimensions, dans le vocabulaire courant de la qualité des données :
complétude (ce qui manque), validité (ce qui est impossible), unicité (ce qui
est en double) et cohérence (ce qui se contredit).

Chaque règle qui vise une anomalie connue déclare le code qu'elle cherche :
c'est ce qui permet, ensuite, de confronter ce qu'on détecte à ce que le
journal d'injection dit avoir posé.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import Select, String, and_, cast, func, not_, or_, select

from anomalies.catalogue import (
    DATE_ANTIDATEE, EMAIL_INVALIDE, MONTANT_ABERRANT, NUMERO_SECU_INVALIDE,
    QUANTITE_EXCESSIVE,
)
from app.models import (
    Agent, InsuredPerson, Invoice, InvoiceProvision, InvoiceStatus,
    PriorAuthorizationMedicalAct,
)

COMPLETUDE = "COMPLETUDE"
VALIDITE = "VALIDITE"
UNICITE = "UNICITE"
COHERENCE = "COHERENCE"

DIMENSIONS = (COMPLETUDE, VALIDITE, UNICITE, COHERENCE)

# Au-delà, un montant de prestation ne peut plus correspondre à un acte réel.
SEUIL_MONTANT_DEMESURE = Decimal("1000000")

# Marge autour de la date de début d'exécution, en jours. Elle doit rester
# au-dessus de l'amplitude de l'aléa d'horloge décalée (72 h), sans quoi un
# passage simplement déphasé serait pris pour une date antidatée.
MARGE_JOURS = 7

# Tolérance sur la recomposition d'un montant, en francs CFA.
TOLERANCE_MONTANT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Regle:
    """Une règle de qualité, et l'anomalie qu'elle cherche s'il y en a une."""

    code: str
    libelle: str
    dimension: str
    # Requête construite pour une exécution donnée. Elle doit ramener des
    # couples (clé métier, valeur fautive).
    requete: Callable[[UUID | None, date | None], Select]
    anomalie_code: str | None = None
    # Vrai quand la règle porte sur le référentiel, qui n'appartient à aucune
    # exécution : le seed le corrompt avant qu'aucune n'existe.
    referentielle: bool = False


@dataclass(frozen=True, slots=True)
class Constat:
    """Une ligne fautive relevée par une règle."""

    regle_code: str
    cle: str
    valeur: Any


def _portee(requete: Select, modele, simulation_id: UUID | None) -> Select:
    """Restreint une requête aux lignes d'une exécution, s'il y en a une."""

    if simulation_id is None:
        return requete
    return requete.where(modele.simulation_id == simulation_id)


# ── Validité des montants ────────────────────────────────────────────────

def _montant_negatif(simulation_id, _debut):
    return _portee(
        select(InvoiceProvision.facture_numero, InvoiceProvision.prestation_montant_depense)
        .where(InvoiceProvision.prestation_montant_depense < 0),
        InvoiceProvision, simulation_id,
    )


def _montant_demesure(simulation_id, _debut):
    return _portee(
        select(InvoiceProvision.facture_numero, InvoiceProvision.prestation_montant_depense)
        .where(InvoiceProvision.prestation_montant_depense > SEUIL_MONTANT_DEMESURE),
        InvoiceProvision, simulation_id,
    )


def _montant_entente_aberrant(simulation_id, _debut):
    return _portee(
        select(
            cast(PriorAuthorizationMedicalAct.entente_prealable_id, String),
            PriorAuthorizationMedicalAct.acte_medical_base_remboursement,
        ).where(or_(
            PriorAuthorizationMedicalAct.acte_medical_base_remboursement < 0,
            PriorAuthorizationMedicalAct.acte_medical_base_remboursement > SEUIL_MONTANT_DEMESURE,
        )),
        PriorAuthorizationMedicalAct, simulation_id,
    )


# ── Validité des dates ───────────────────────────────────────────────────

def _date_antidatee(simulation_id, debut):
    requete = select(Invoice.facture_numero, Invoice.facture_date_soins)
    if debut is not None:
        requete = requete.where(Invoice.facture_date_soins < debut - timedelta(days=MARGE_JOURS))
    return _portee(requete, Invoice, simulation_id)


def _date_future(simulation_id, debut):
    requete = select(Invoice.facture_numero, Invoice.facture_date_soins)
    if debut is not None:
        requete = requete.where(Invoice.facture_date_soins > debut + timedelta(days=MARGE_JOURS))
    return _portee(requete, Invoice, simulation_id)


# ── Cohérence ────────────────────────────────────────────────────────────

def _quantite_excessive(simulation_id, _debut):
    return _portee(
        select(InvoiceProvision.facture_numero, InvoiceProvision.prestation_quantite_servie)
        .where(InvoiceProvision.prestation_quantite_servie
               > InvoiceProvision.prestation_quantite_prescrite),
        InvoiceProvision, simulation_id,
    )


def _repartition_incoherente(simulation_id, _debut):
    """La part CMU et la part assuré doivent recomposer la base remboursable."""

    ecart = func.abs(
        InvoiceProvision.prestation_base_remboursement
        - InvoiceProvision.prestation_montant_rq
        - InvoiceProvision.prestation_montant_assure
    )
    return _portee(
        select(InvoiceProvision.facture_numero, ecart)
        .where(and_(
            InvoiceProvision.prestation_base_remboursement.is_not(None),
            InvoiceProvision.prestation_montant_rq.is_not(None),
            InvoiceProvision.prestation_montant_assure.is_not(None),
            ecart > TOLERANCE_MONTANT,
        )),
        InvoiceProvision, simulation_id,
    )


def _facture_sans_cloture(simulation_id, _debut):
    """Une facture ouverte que rien n'a clôturée : trace d'une coupure."""

    clôturees = select(InvoiceStatus.facture_numero).where(
        InvoiceStatus.statut_code == "cloturee"
    )
    return _portee(
        select(Invoice.facture_numero, Invoice.facture_date_soins)
        .where(not_(Invoice.facture_numero.in_(clôturees))),
        Invoice, simulation_id,
    )


# ── Complétude ───────────────────────────────────────────────────────────

def _facture_sans_prestation(simulation_id, _debut):
    servies = select(InvoiceProvision.facture_numero)
    return _portee(
        select(Invoice.facture_numero, Invoice.type_facture_code)
        .where(not_(Invoice.facture_numero.in_(servies))),
        Invoice, simulation_id,
    )


def _facture_sans_regime(simulation_id, _debut):
    return _portee(
        select(Invoice.facture_numero, Invoice.regime_code)
        .where(or_(Invoice.regime_code.is_(None), Invoice.regime_taux.is_(None))),
        Invoice, simulation_id,
    )


# ── Référentiel : ce que le seed a corrompu ──────────────────────────────

def _numero_secu_invalide(_simulation_id, _debut):
    return select(InsuredPerson.assure_numero_identifiant, InsuredPerson.numero_secu).where(
        or_(
            InsuredPerson.numero_secu.op("!~")(r"^\d{13,14}$"),
            InsuredPerson.numero_secu == "00000000000000",
        )
    )


def _email_agent_invalide(_simulation_id, _debut):
    return select(Agent.agent_code, Agent.agent_email).where(
        or_(Agent.agent_email.is_(None), Agent.agent_email.not_like("%@%.%"))
    )


def _identite_en_double(_simulation_id, _debut):
    """Deux assurés qui portent la même identité civile.

    Le numéro de sécurité sociale ne convient pas comme signal d'unicité : la
    base l'interdit déjà par contrainte, un doublon ne peut donc pas s'y
    former. L'identité civile, elle, n'est protégée par rien — et c'est
    exactement le doublon que le rapprochement d'identités doit retrouver.
    """

    return (
        select(
            func.concat(
                InsuredPerson.assure_nom, " ", InsuredPerson.assure_prenoms,
                " (", func.cast(InsuredPerson.assure_date_naissance, String), ")",
            ),
            func.count(),
        )
        .group_by(
            InsuredPerson.assure_nom,
            InsuredPerson.assure_prenoms,
            InsuredPerson.assure_date_naissance,
        )
        .having(func.count() > 1)
    )


REGLES: tuple[Regle, ...] = (
    Regle("MONTANT_NEGATIF", "Montant de prestation négatif", VALIDITE,
          _montant_negatif, MONTANT_ABERRANT),
    Regle("MONTANT_DEMESURE", "Montant de prestation hors de toute échelle", VALIDITE,
          _montant_demesure, MONTANT_ABERRANT),
    Regle("MONTANT_ENTENTE_ABERRANT", "Montant d'acte sous entente aberrant", VALIDITE,
          _montant_entente_aberrant, MONTANT_ABERRANT),
    Regle("DATE_SOINS_ANTIDATEE", "Date de soins bien antérieure à l'exécution", VALIDITE,
          _date_antidatee, DATE_ANTIDATEE),
    Regle("DATE_SOINS_FUTURE", "Date de soins postérieure à l'exécution", VALIDITE,
          _date_future, None),
    Regle("QUANTITE_SERVIE_EXCESSIVE", "Quantité servie supérieure à la prescrite", COHERENCE,
          _quantite_excessive, QUANTITE_EXCESSIVE),
    Regle("REPARTITION_INCOHERENTE", "Part CMU et part assuré ne recomposent pas la base",
          COHERENCE, _repartition_incoherente, None),
    Regle("FACTURE_SANS_CLOTURE", "Facture ouverte jamais clôturée", COHERENCE,
          _facture_sans_cloture, None),
    Regle("FACTURE_SANS_PRESTATION", "Facture sans aucune prestation", COMPLETUDE,
          _facture_sans_prestation, None),
    Regle("FACTURE_SANS_REGIME", "Facture sans régime ou sans taux", COMPLETUDE,
          _facture_sans_regime, None),
    Regle("NUMERO_SECU_INVALIDE", "Numéro de sécurité sociale mal formé", VALIDITE,
          _numero_secu_invalide, NUMERO_SECU_INVALIDE, referentielle=True),
    Regle("EMAIL_AGENT_INVALIDE", "Adresse électronique d'agent mal formée", VALIDITE,
          _email_agent_invalide, EMAIL_INVALIDE, referentielle=True),
    Regle("IDENTITE_EN_DOUBLE", "Même identité civile sur plusieurs assurés", UNICITE,
          _identite_en_double, None, referentielle=True),
)
