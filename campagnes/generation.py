"""Pilote la génération d'un jeu de campagne : état, progression, corrigé.

Le calcul lui-même est dans `campagnes/generateur.py`. Ce module s'occupe de ce
qui l'entoure : ne pas lancer deux générations sur la même campagne, tenir une
progression consultable pendant que ça tourne, verser le corrigé en base et
inscrire l'empreinte sur la campagne.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select

from app.database import async_session_factory
from campagnes.generateur import (
    TAILLE_LOT_CORRIGE, Constat, chemin_du_jeu, horodatage, produire,
)
from campagnes.models import (
    STATUT_CREEE, STATUT_GENERATION, STATUT_GENEREE, Campagne, CorrigeCampagne,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Progression:
    """Où en est une génération, pendant qu'elle tourne.

    Gardée en mémoire et non en base : c'est une information de l'instant,
    consultée toutes les secondes par l'écran. L'écrire en base à chaque pas
    coûterait plus cher que de produire les lignes.
    """

    volume_cible: int
    lignes_generees: int = 0
    anomalies_posees: int = 0
    terminee: bool = False
    erreur: str | None = None

    @property
    def pourcentage(self) -> float:
        if self.volume_cible <= 0:
            return 100.0
        return round(100 * self.lignes_generees / self.volume_cible, 1)


# Les générations en cours, par campagne. Un dictionnaire de processus suffit :
# une génération ne survit pas au redémarrage de l'API, et une campagne
# interrompue se relance.
PROGRESSIONS: dict[UUID, Progression] = {}
_taches: dict[UUID, asyncio.Task] = {}


def progression(campagne_id: UUID) -> Progression | None:
    """Retourne la progression d'une génération en cours, s'il y en a une."""

    return PROGRESSIONS.get(campagne_id)


async def _verser_corrige(campagne_id: UUID, constats: list[Constat]) -> None:
    """Écrit le corrigé, par lots, après avoir effacé le précédent.

    Effacer d'abord : régénérer une campagne avec la même graine reproduit les
    mêmes constats, et la clé primaire les refuserait en double.
    """

    async with async_session_factory() as session:
        await session.execute(
            delete(CorrigeCampagne).where(CorrigeCampagne.campagne_id == campagne_id)
        )
        for depart in range(0, len(constats), TAILLE_LOT_CORRIGE):
            lot = constats[depart:depart + TAILLE_LOT_CORRIGE]
            session.add_all([
                CorrigeCampagne(
                    campagne_id=campagne_id,
                    corrige_ligne=constat.ligne,
                    anomalie_code=constat.anomalie_code,
                    corrige_champ=constat.champ,
                    corrige_valeur_origine=constat.valeur_origine,
                    corrige_valeur_injectee=constat.valeur_injectee,
                    utilisateur_id_creation="campagnes",
                )
                for constat in lot
            ])
            await session.flush()
        await session.commit()


async def _executer(campagne_id: UUID, graine: int, volume: int,
                    reglages: dict[str, dict], destination: Path,
                    suivi: Progression) -> None:
    """Produit le jeu hors de la boucle d'événements, puis range le résultat.

    La production est un calcul long et purement synchrone : la laisser dans la
    boucle figerait l'API — plus de progression consultable, plus de connexion
    temps réel, exactement pendant les minutes où l'on veut regarder.
    """

    try:
        empreinte, constats, lignes = await asyncio.to_thread(
            produire, graine, volume, reglages, destination,
            lambda faites: setattr(suivi, "lignes_generees", faites),
        )
        suivi.anomalies_posees = len(constats)

        await _verser_corrige(campagne_id, constats)

        async with async_session_factory() as session:
            campagne = await session.get(Campagne, campagne_id)
            if campagne is not None:
                campagne.campagne_statut = STATUT_GENEREE
                campagne.campagne_date_generation = horodatage()
                campagne.campagne_lignes_generees = lignes
                campagne.campagne_anomalies_posees = len(constats)
                campagne.campagne_empreinte = empreinte
                campagne.campagne_fichier = str(destination).replace("\\", "/")
                await session.commit()
        suivi.terminee = True

    except Exception as erreur:  # noqa: BLE001 — l'écran doit voir la panne
        logger.exception("Génération de la campagne %s interrompue", campagne_id)
        suivi.erreur = str(erreur)
        suivi.terminee = True
        async with async_session_factory() as session:
            campagne = await session.get(Campagne, campagne_id)
            if campagne is not None:
                # Retour à « créée » : une campagne à moitié générée serait
                # silencieusement incomplète, ce que le cahier interdit.
                campagne.campagne_statut = STATUT_CREEE
                await session.commit()
    finally:
        _taches.pop(campagne_id, None)


async def lancer(campagne_id: UUID) -> Progression:
    """Démarre la génération d'une campagne et retourne sa progression.

    Refuse une seconde génération simultanée : deux écritures sur le même
    fichier produiraient un jeu illisible et un corrigé faux.
    """

    tache = _taches.get(campagne_id)
    if tache is not None and not tache.done():
        raise RuntimeError("Cette campagne est déjà en cours de génération.")

    async with async_session_factory() as session:
        campagne = await session.get(Campagne, campagne_id)
        if campagne is None:
            raise LookupError(f"Campagne inconnue : {campagne_id}.")

        reglages = dict((campagne.campagne_parametres or {}).get("anomalies", {}))
        graine = campagne.campagne_graine
        volume = campagne.campagne_volume_cible
        destination = chemin_du_jeu(campagne_id, campagne.campagne_reference)

        campagne.campagne_statut = STATUT_GENERATION
        campagne.campagne_empreinte = None
        campagne.campagne_lignes_generees = 0
        campagne.campagne_anomalies_posees = 0
        await session.commit()

    suivi = Progression(volume_cible=volume)
    PROGRESSIONS[campagne_id] = suivi
    _taches[campagne_id] = asyncio.create_task(
        _executer(campagne_id, graine, volume, reglages, destination, suivi)
    )
    return suivi


async def lire_corrige(campagne_id: UUID, limite: int = 50, decalage: int = 0,
                       anomalie_code: str | None = None) -> list[CorrigeCampagne]:
    """Retourne des lignes du corrigé, de la première à la dernière.

    Trié par ligne puis par type : un corrigé qui change d'ordre entre deux
    consultations serait illisible, et deux anomalies peuvent viser la même
    ligne.
    """

    async with async_session_factory() as session:
        requete = select(CorrigeCampagne).where(
            CorrigeCampagne.campagne_id == campagne_id
        )
        if anomalie_code:
            requete = requete.where(CorrigeCampagne.anomalie_code == anomalie_code)
        resultat = await session.execute(
            requete
            .order_by(CorrigeCampagne.corrige_ligne, CorrigeCampagne.anomalie_code)
            .offset(decalage)
            .limit(limite)
        )
        return list(resultat.scalars().all())


async def compter_corrige(campagne_id: UUID) -> dict[str, int]:
    """Compte les anomalies posées, par type.

    C'est la moitié gauche du futur tableau de score : « injectées », face aux
    « vrais positifs » que le rapport de l'outil testé fournira.
    """

    async with async_session_factory() as session:
        resultat = await session.execute(
            select(CorrigeCampagne.anomalie_code, func.count())
            .where(CorrigeCampagne.campagne_id == campagne_id)
            .group_by(CorrigeCampagne.anomalie_code)
            .order_by(CorrigeCampagne.anomalie_code)
        )
        return {code: nombre for code, nombre in resultat.all()}
