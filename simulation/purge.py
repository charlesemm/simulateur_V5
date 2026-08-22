"""Supprime les données produites par une exécution.

ÉCHO conserve toutes les lignes de chaque exécution : c'est la décision de
départ. La purge est donc la seule sortie, et elle doit être exacte — ni
laisser d'orphelin, ni emporter une ligne d'une autre exécution.

L'ordre de suppression suit les clés étrangères, y compris le cycle entre la
facture et son entente préalable : la facture cesse d'abord de désigner son
entente, sinon aucune des deux ne peut disparaître.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, func, select, update

from anomalies.models import AnomalyInjection
from app.database import async_session_factory
from app.models import (
    Invoice, InvoicePathology, InvoicePrescription, InvoiceProvision,
    InvoiceStatus, PriorAuthorization, PriorAuthorizationMedicalAct,
    PriorAuthorizationProvision, PriorAuthorizationStatus,
)
from events.models import EventJournal
from simulation.models import RefusAccueil, SimulationRun

logger = logging.getLogger(__name__)

# Ordre de suppression : les enfants avant leurs parents.
TABLES = (
    ("statuts_ententes", PriorAuthorizationStatus),
    ("actes_ententes", PriorAuthorizationMedicalAct),
    ("prestations_ententes", PriorAuthorizationProvision),
    ("ententes", PriorAuthorization),
    ("statuts_factures", InvoiceStatus),
    ("prestations", InvoiceProvision),
    ("pathologies", InvoicePathology),
    ("prescriptions", InvoicePrescription),
    ("factures", Invoice),
    ("evenements", EventJournal),
    ("anomalies", AnomalyInjection),
    ("refus_accueil", RefusAccueil),
)


async def compter(simulation_id: uuid.UUID) -> dict[str, int]:
    """Compte ce qu'une purge supprimerait, sans rien toucher."""

    async with async_session_factory() as session:
        return {
            nom: (await session.execute(
                select(func.count()).select_from(modele)
                .where(modele.simulation_id == simulation_id)
            )).scalar_one()
            for nom, modele in TABLES
        }


async def purger(simulation_id: uuid.UUID) -> dict[str, int]:
    """Supprime les lignes produites par une exécution et retourne le compte.

    L'exécution elle-même est conservée : son statut et ses compteurs restent
    l'historique de ce qui a eu lieu, même une fois les données parties.
    """

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)
        if execution is None:
            raise LookupError(f"Exécution inconnue : {simulation_id}.")

        # Le cycle facture-entente doit être rompu avant toute suppression.
        await session.execute(
            update(Invoice)
            .where(Invoice.simulation_id == simulation_id)
            .values(entente_prealable_id=None)
        )

        supprimees: dict[str, int] = {}
        for nom, modele in TABLES:
            resultat = await session.execute(
                delete(modele).where(modele.simulation_id == simulation_id)
            )
            supprimees[nom] = resultat.rowcount or 0

        await session.commit()

    total = sum(supprimees.values())
    logger.info("Purge de l'exécution %s : %s ligne(s) supprimée(s).", simulation_id, total)
    supprimees["total"] = total
    return supprimees
