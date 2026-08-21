"""Reconstitue le parcours d'un passage à partir du journal d'événements.

Le moteur ne stocke nulle part la suite des étapes franchies : elle n'existe
que sous forme d'événements dans TB_EVENEMENTS_METIER, indexés par PASSAGE_ID.
Ce module les relit dans l'ordre de l'horloge simulée et les traduit en
étapes lisibles.
"""
from __future__ import annotations

from sqlalchemy import select

from app.database import async_session_factory
from api.schema import ParcoursEtapeSchema, ParcoursResponse
from events.models import EventJournal

# Traduction des types techniques du bus en libellés affichables. Un type
# inconnu retombe sur son propre nom plutôt que de disparaître.
LIBELLES_ETAPES = {
    "facture.creee": "Ouverture de la facture",
    "facture.pathologies": "Diagnostic saisi",
    "facture.statut": "Changement de statut",
    "prestation.servie": "Prestation servie",
    "medicament.prescrit": "Médicament prescrit",
    "medicament.retire": "Médicament retiré en pharmacie",
    "entente.creee": "Demande d'entente préalable",
    "entente.traitee": "Décision du médecin conseil",
    "passage.refuse": "Présentation refusée à l'accueil",
}


def libelle_etape(evenement: EventJournal) -> str:
    """Donne le libellé d'une étape, en précisant le statut quand il y en a un."""

    libelle = LIBELLES_ETAPES.get(evenement.type_evenement, evenement.type_evenement)
    statut = evenement.payload.get("statut")
    return f"{libelle} : {statut}" if statut else libelle


async def find_passage_id(facture_numero: str) -> str | None:
    """Retrouve le passage qui a produit une facture donnée.

    Le numéro de facture voyage dans la charge utile des événements ; c'est le
    seul lien entre une facture et le passage qui l'a ouverte.
    """

    async with async_session_factory() as session:
        return (await session.execute(
            select(EventJournal.passage_id)
            .where(EventJournal.payload["facture_numero"].astext == facture_numero)
            .limit(1)
        )).scalar_one_or_none()


async def build_parcours(passage_id: str) -> ParcoursResponse | None:
    """Assemble les étapes d'un passage, ou None s'il n'a rien produit."""

    async with async_session_factory() as session:
        evenements = list((await session.execute(
            select(EventJournal)
            .where(EventJournal.passage_id == passage_id)
            .order_by(EventJournal.simulated_at, EventJournal.date_creation)
        )).scalars())

    if not evenements:
        return None

    facture_numero = next(
        (event.payload["facture_numero"] for event in evenements
         if "facture_numero" in event.payload),
        None,
    )
    debut, fin = evenements[0].simulated_at, evenements[-1].simulated_at
    return ParcoursResponse(
        passage_id=passage_id,
        facture_numero=facture_numero,
        debut=debut,
        fin=fin,
        duree_simulee_secondes=(fin - debut).total_seconds(),
        nombre_etapes=len(evenements),
        etapes=[
            ParcoursEtapeSchema(
                ordre=ordre,
                type_evenement=event.type_evenement,
                libelle=libelle_etape(event),
                simulated_at=event.simulated_at,
                payload=event.payload,
            )
            for ordre, event in enumerate(evenements, start=1)
        ],
    )
