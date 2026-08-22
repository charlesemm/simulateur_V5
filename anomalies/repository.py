"""Charge et sauvegarde le réglage, le catalogue et le journal des anomalies."""
from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from anomalies.config import Injection, Reglage, anomalies_config
from anomalies.models import AnomaliesConfigRow, AnomalyInjection, AnomalyType
from app.database import async_session_factory

logger = logging.getLogger(__name__)

# La table de réglage ne contient qu'une seule ligne, identifiée par cette clé.
CONFIG_ID = 1


async def charger_configuration() -> None:
    """Restaure la configuration persistée dans l'instance en mémoire."""

    async with async_session_factory() as session:
        ligne = await session.get(AnomaliesConfigRow, CONFIG_ID)
        if ligne is None:
            logger.info(
                "Aucune configuration d'anomalies en base : valeurs par défaut."
            )
            return
        anomalies_config.enabled = ligne.enabled
        anomalies_config.rate = float(ligne.rate)
        anomalies_config.severity = ligne.severity
        anomalies_config.injected_count = ligne.injected_count
    logger.info(
        "Configuration d'anomalies restaurée (activee=%s, taux=%s, injectees=%s).",
        anomalies_config.enabled,
        anomalies_config.rate,
        anomalies_config.injected_count,
    )


async def sauvegarder_configuration() -> None:
    """Écrit l'état courant de l'instance en mémoire dans la base."""

    async with async_session_factory() as session:
        ligne = await session.get(AnomaliesConfigRow, CONFIG_ID)
        if ligne is None:
            ligne = AnomaliesConfigRow(config_id=CONFIG_ID)
            session.add(ligne)
        ligne.enabled = anomalies_config.enabled
        ligne.rate = Decimal(str(round(anomalies_config.rate, 2)))
        ligne.severity = anomalies_config.severity
        ligne.injected_count = anomalies_config.injected_count
        await session.commit()


async def charger_catalogue() -> None:
    """Recopie le catalogue en mémoire, pour que le moteur le lise sans requête.

    Un type absent de la base garde son réglage par défaut : le moteur n'a
    jamais à décider ce qu'il ferait d'un catalogue incomplet.
    """

    async with async_session_factory() as session:
        types = (await session.execute(select(AnomalyType))).scalars().all()

    for type_anomalie in types:
        anomalies_config.reglages[type_anomalie.anomalie_code] = Reglage(
            active=type_anomalie.anomalie_active,
            taux=float(type_anomalie.anomalie_taux),
            declenchement=type_anomalie.anomalie_declenchement,
            delai_secondes=type_anomalie.anomalie_delai_secondes,
        )
    logger.info("Catalogue d'anomalies chargé : %s type(s).", len(types))


async def lire_catalogue() -> list[AnomalyType]:
    """Retourne le catalogue tel qu'il est en base, trié par code."""

    async with async_session_factory() as session:
        return list((await session.execute(
            select(AnomalyType).order_by(AnomalyType.anomalie_code)
        )).scalars())


async def modifier_type(code: str, active: bool | None = None,
                        taux: float | None = None,
                        declenchement: str | None = None,
                        delai_secondes: int | None = None) -> AnomalyType | None:
    """Change le réglage d'un type, en base et en mémoire."""

    async with async_session_factory() as session:
        type_anomalie = await session.get(AnomalyType, code)
        if type_anomalie is None:
            return None
        if active is not None:
            type_anomalie.anomalie_active = active
        if taux is not None:
            type_anomalie.anomalie_taux = Decimal(str(round(taux, 2)))
        if declenchement is not None:
            type_anomalie.anomalie_declenchement = declenchement
        if delai_secondes is not None:
            type_anomalie.anomalie_delai_secondes = delai_secondes
        await session.commit()
        await session.refresh(type_anomalie)

    # L'état armé ne vient pas de la base : c'est un ordre de l'opérateur, qui
    # ne vaut que pour l'exécution en cours.
    arme = anomalies_config.reglage(code).arme
    anomalies_config.reglages[code] = Reglage(
        active=type_anomalie.anomalie_active,
        taux=float(type_anomalie.anomalie_taux),
        declenchement=type_anomalie.anomalie_declenchement,
        delai_secondes=type_anomalie.anomalie_delai_secondes,
        arme=arme,
    )
    return type_anomalie


def appliquer_profil(anomalies: dict[str, dict]) -> None:
    """Applique en mémoire les réglages d'anomalies d'un profil de simulation.

    Volontairement sans écriture : lancer un type de simulation ne doit pas
    écraser en base le catalogue que l'opérateur a réglé à la main. Le profil
    vaut pour l'exécution, le catalogue reste la référence.
    """

    for code, valeurs in anomalies.items():
        reglage = anomalies_config.reglage(code)
        anomalies_config.reglages[code] = Reglage(
            active=valeurs.get("active", True),
            taux=valeurs.get("taux", reglage.taux),
            declenchement=valeurs.get("declenchement", reglage.declenchement),
            delai_secondes=valeurs.get("delai_secondes", reglage.delai_secondes),
        )


async def enregistrer_injections(injections: Iterable[Injection],
                                 session: AsyncSession | None = None) -> int:
    """Écrit les injections consignées dans le journal, et retourne leur nombre.

    Une session peut être fournie pour que le journal parte dans la même
    transaction que les lignes corrompues — c'est le cas du seed.
    """

    lignes = [
        AnomalyInjection(
            injection_id=uuid.uuid4(),
            anomalie_code=injection.anomalie_code,
            simulation_id=injection.simulation_id,
            passage_id=injection.passage_id,
            cible_cle=injection.cible_cle,
            valeur_origine=injection.valeur_origine,
            valeur_injectee=injection.valeur_injectee,
            utilisateur_id_creation="anomalies",
        )
        for injection in injections
    ]
    if not lignes:
        return 0

    if session is not None:
        session.add_all(lignes)
        return len(lignes)

    async with async_session_factory() as propre_session:
        propre_session.add_all(lignes)
        await propre_session.commit()
    return len(lignes)
