"""T1 — Moteur de qualité des données.

Applique les règles aux données d'une exécution, puis confronte ce qu'il
détecte à ce que le journal d'injection dit avoir posé. Cette confrontation
est tout l'intérêt d'ÉCHO : un outil de qualité branché sur des données réelles
ne peut jamais dire combien de défauts lui ont échappé.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from anomalies.models import AnomalyInjection, AnomalyType
from app.database import async_session_factory
from qualite.regles import DIMENSIONS, REGLES, Regle
from simulation.models import SimulationRun

logger = logging.getLogger(__name__)

# Nombre de lignes fautives conservées en exemple par règle : le rapport
# montre de quoi il parle sans recopier des milliers de lignes.
EXEMPLES_PAR_REGLE = 3


async def _appliquer(session, regle: Regle, simulation_id: UUID | None,
                     debut) -> tuple[int, list[dict[str, Any]]]:
    """Exécute une règle et retourne son compte et quelques exemples."""

    requete = regle.requete(simulation_id, debut)
    lignes = (await session.execute(requete)).all()
    exemples = [
        {"cle": str(ligne[0]), "valeur": str(ligne[1])}
        for ligne in lignes[:EXEMPLES_PAR_REGLE]
    ]
    return len(lignes), exemples


async def analyser(simulation_id: UUID | None = None,
                   inclure_referentiel: bool = True) -> dict[str, Any]:
    """Produit le rapport de qualité d'une exécution.

    Sans exécution, les règles portent sur l'ensemble des données : c'est le
    mode « tout ce qui est en base », utile avant d'avoir lancé quoi que ce
    soit. Les règles référentielles ignorent de toute façon l'exécution : le
    seed corrompt le référentiel avant qu'aucune n'existe.
    """

    genere_le = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        debut = None
        if simulation_id is not None:
            execution = await session.get(SimulationRun, simulation_id)
            if execution is None:
                raise LookupError(f"Exécution inconnue : {simulation_id}.")
            debut = execution.simulation_date_debut.date()

        resultats: list[dict[str, Any]] = []
        for regle in REGLES:
            if regle.referentielle and not inclure_referentiel:
                continue
            nombre, exemples = await _appliquer(session, regle, simulation_id, debut)
            resultats.append({
                "code": regle.code,
                "libelle": regle.libelle,
                "dimension": regle.dimension,
                "anomalie_visee": regle.anomalie_code,
                "referentielle": regle.referentielle,
                "constats": nombre,
                "exemples": exemples,
            })

        # Vérité terrain : ce que le journal dit avoir été injecté.
        requete_journal = select(AnomalyInjection.anomalie_code, func.count()).group_by(
            AnomalyInjection.anomalie_code
        )
        if simulation_id is not None:
            requete_journal = requete_journal.where(
                AnomalyInjection.simulation_id == simulation_id
            )
        injectees = dict((await session.execute(requete_journal)).all())

        # Taux demandé : celui que l'exécution portait dans ses paramètres,
        # à défaut celui du catalogue. C'est à lui que se compare le taux
        # réellement constaté.
        demandes = {
            code: float(taux)
            for code, taux in (await session.execute(
                select(AnomalyType.anomalie_code, AnomalyType.anomalie_taux)
            )).all()
        }
        if simulation_id is not None:
            for code, valeurs in (execution.simulation_parametres or {}).get(
                "anomalies", {}
            ).items():
                if isinstance(valeurs, dict) and "taux" in valeurs:
                    demandes[code] = float(valeurs["taux"])

    par_dimension = {
        dimension: sum(
            resultat["constats"] for resultat in resultats
            if resultat["dimension"] == dimension
        )
        for dimension in DIMENSIONS
    }

    return {
        "simulation_id": str(simulation_id) if simulation_id else None,
        "genere_le": genere_le.isoformat(),
        "total_constats": sum(resultat["constats"] for resultat in resultats),
        "par_dimension": par_dimension,
        "regles": resultats,
        "confrontation": _confronter(resultats, injectees, demandes),
    }


def _confronter(resultats: list[dict[str, Any]], injectees: dict[str, int],
                demandes: dict[str, float]) -> list[dict[str, Any]]:
    """Compare, type par type, ce qui est détecté à ce qui a été injecté.

    Le taux de détection n'est pas un score de justesse : une règle peut
    relever une ligne que personne n'a corrompue — une date antidatée de moins
    d'une semaine échappe au contraire à sa règle, par construction. C'est
    précisément ce que la confrontation sert à rendre visible.
    """

    detectees: dict[str, int] = {}
    regles_par_anomalie: dict[str, list[str]] = {}
    for resultat in resultats:
        code = resultat["anomalie_visee"]
        if code is None:
            continue
        detectees[code] = detectees.get(code, 0) + resultat["constats"]
        regles_par_anomalie.setdefault(code, []).append(resultat["code"])

    lignes = []
    for code in sorted(set(detectees) | set(injectees)):
        nombre_injectees = injectees.get(code, 0)
        nombre_detectees = detectees.get(code, 0)
        lignes.append({
            "anomalie_code": code,
            "taux_demande_pourcent": round(100 * demandes.get(code, 0.0), 1),
            "injectees": nombre_injectees,
            "detectees": nombre_detectees,
            "taux_detection_pourcent": (
                round(100 * nombre_detectees / nombre_injectees, 1)
                if nombre_injectees else None
            ),
            "regles": regles_par_anomalie.get(code, []),
        })
    return lignes
