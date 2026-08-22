"""Lecture de la vérité terrain et notation d'un rapprochement proposé."""

from __future__ import annotations

import uuid
from typing import Any, Iterable

from sqlalchemy import select

from app.database import async_session_factory
from mdm.models import MdmPair


def _clef(premier: uuid.UUID | str, second: uuid.UUID | str) -> tuple[str, str]:
    """Ordonne une paire : le sens du rapprochement n'a pas de sens."""

    gauche, droite = str(premier), str(second)
    return (gauche, droite) if gauche <= droite else (droite, gauche)


async def lire_paires(simulation_id: uuid.UUID | None = None) -> list[MdmPair]:
    """Retourne la vérité terrain, éventuellement limitée à une exécution."""

    async with async_session_factory() as session:
        requete = select(MdmPair).order_by(MdmPair.date_creation.desc())
        if simulation_id is not None:
            requete = requete.where(MdmPair.simulation_id == simulation_id)
        return list((await session.execute(requete)).scalars())


async def evaluer(paires_proposees: Iterable[tuple[str, str]],
                  simulation_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Note un rapprochement proposé contre la vérité terrain.

    Trois chiffres, dans le vocabulaire habituel :
      — la précision dit quelle part des paires proposées était juste ;
      — le rappel dit quelle part des vrais doublons a été retrouvée ;
      — la F-mesure les résume d'un seul nombre.

    Les paires que la vérité terrain ne connaît pas sont écartées du calcul :
    ÉCHO ne peut se prononcer que sur ce qu'il a lui-même fabriqué, et compter
    l'inconnu comme une erreur serait un procès injuste.
    """

    verite = await lire_paires(simulation_id)
    attendues = {
        _clef(paire.personne_uuid_source, paire.personne_uuid_variante): paire.meme_personne
        for paire in verite
    }

    proposees = {_clef(gauche, droite) for gauche, droite in paires_proposees}
    connues = {paire for paire in proposees if paire in attendues}
    hors_perimetre = len(proposees) - len(connues)

    vrais_positifs = sum(1 for paire in connues if attendues[paire])
    faux_positifs = sum(1 for paire in connues if not attendues[paire])
    doublons_reels = sum(1 for meme in attendues.values() if meme)
    faux_negatifs = doublons_reels - vrais_positifs

    precision = (
        vrais_positifs / (vrais_positifs + faux_positifs)
        if vrais_positifs + faux_positifs else None
    )
    rappel = vrais_positifs / doublons_reels if doublons_reels else None
    f_mesure = (
        2 * precision * rappel / (precision + rappel)
        if precision and rappel else None
    )

    return {
        "simulation_id": str(simulation_id) if simulation_id else None,
        "paires_connues": len(attendues),
        "doublons_reels": doublons_reels,
        "leurres": len(attendues) - doublons_reels,
        "paires_proposees": len(proposees),
        "hors_perimetre": hors_perimetre,
        "vrais_positifs": vrais_positifs,
        "faux_positifs": faux_positifs,
        "faux_negatifs": faux_negatifs,
        "precision_pourcent": None if precision is None else round(100 * precision, 1),
        "rappel_pourcent": None if rappel is None else round(100 * rappel, 1),
        "f_mesure_pourcent": None if f_mesure is None else round(100 * f_mesure, 1),
    }
