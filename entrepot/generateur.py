"""T3 — Profondeur d'historique pour éprouver les chargements d'entrepôt.

Ce type ne cherche pas le défaut mais le volume et la durée : plusieurs mois
de droits, et des périodes de profession qui se succèdent proprement.

Le motif SCD2 déjà en place sur les référentiels est respecté à la lettre : une
période est fermée avant que la suivante ne s'ouvre. Les contraintes
d'exclusion posées par la migration 0007 l'imposent de toute façon — un
recouvrement serait rejeté par la base, ce qui est exactement le garde-fou
qu'un entrepôt attend d'une source.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import InsuredPerson, InsuredProfession, InsuredRight
from seed.constants import PROFESSIONS
from seed.identifiants import numero_libre

logger = logging.getLogger(__name__)


def _mois_precedents(nombre: int) -> list[tuple[int, int]]:
    """Retourne les couples (année, mois) des N mois précédant celui-ci."""

    aujourdhui = datetime.now(timezone.utc)
    mois: list[tuple[int, int]] = []
    annee, numero = aujourdhui.year, aujourdhui.month
    for _ in range(nombre):
        numero -= 1
        if numero == 0:
            annee, numero = annee - 1, 12
        mois.append((annee, numero))
    return mois


async def approfondir_historique(mois: int = 12, assures: int = 50,
                                 simulation_id: uuid.UUID | None = None,
                                 graine: int = 42) -> dict[str, int]:
    """Ajoute des mois de droits et des versions de profession.

    Retourne le compte de ce qui a été écrit. Rien n'écrase l'existant : un
    mois déjà présent est laissé tel quel, et une profession n'est versionnée
    que si sa période courante est encore ouverte.
    """

    if mois < 1:
        raise ValueError("Il faut au moins un mois d'historique.")

    tirage = random.Random(graine)
    periodes = _mois_precedents(mois)
    # Chaque entrée du référentiel porte (code, libellé, régime cible).
    codes_profession = [entree[0] for entree in PROFESSIONS]
    droits_ecrits = 0
    versions_ecrites = 0

    async with async_session_factory() as session:
        echantillon = list((await session.execute(
            select(InsuredPerson).order_by(func.random()).limit(assures)
        )).scalars())
        if not echantillon:
            raise RuntimeError("Aucun assuré en base : lancez le seed d'abord.")

        for personne in echantillon:
            existants = set((await session.execute(
                select(InsuredRight.droits_annee, InsuredRight.droits_mois)
                .where(InsuredRight.personne_uuid == personne.personne_uuid)
            )).all())

            for annee, numero in periodes:
                if (annee, numero) in existants:
                    continue
                debut = datetime(annee, numero, 1, tzinfo=timezone.utc)
                session.add(InsuredRight(
                    personne_uuid=personne.personne_uuid,
                    droits_annee=annee,
                    droits_mois=numero,
                    droits_id=numero_libre("droits", tirage),
                    # Les droits s'ouvrent et se ferment au fil des mois : un
                    # historique uniformément ouvert n'éprouverait rien.
                    droits_statut=1 if tirage.random() < 0.75 else 0,
                    droits_date_debut=debut,
                    utilisateur_id_creation="entrepot",
                ))
                droits_ecrits += 1

            versions_ecrites += await _versionner_profession(
                session, personne, codes_profession, tirage
            )

        await session.commit()

    logger.info("Entrepôt : %s droits et %s versions de profession.",
                droits_ecrits, versions_ecrites)
    return {
        "assures_traites": len(echantillon),
        "mois_demandes": mois,
        "droits_ecrits": droits_ecrits,
        "versions_profession": versions_ecrites,
        "simulation_id": str(simulation_id) if simulation_id else None,
    }


async def _versionner_profession(session, personne: InsuredPerson,
                                 codes: list[str], tirage: random.Random) -> int:
    """Ferme la profession courante et en ouvre une nouvelle.

    C'est le mouvement que tout chargement SCD2 doit savoir suivre : une ligne
    fermée, une ligne ouverte, sans recouvrement d'un instant.
    """

    if not codes:
        return 0

    courante = (await session.execute(
        select(InsuredProfession)
        .where(
            InsuredProfession.personne_uuid == personne.personne_uuid,
            InsuredProfession.profession_date_fin.is_(None),
        )
        .order_by(InsuredProfession.profession_date_debut.desc())
        .limit(1)
    )).scalar_one_or_none()

    if courante is None:
        return 0

    nouveau_code = tirage.choice(codes)
    if nouveau_code == courante.profession_code:
        return 0

    bascule = datetime.now(timezone.utc) - timedelta(days=tirage.randrange(30, 900))
    if bascule <= courante.profession_date_debut:
        # La bascule doit tomber après le début de la période en cours, sans
        # quoi les deux versions se recouvriraient.
        return 0

    courante.profession_date_fin = bascule
    session.add(InsuredProfession(
        personne_uuid=personne.personne_uuid,
        profession_code=nouveau_code,
        profession_date_debut=bascule,
        utilisateur_id_creation="entrepot",
    ))
    return 1
