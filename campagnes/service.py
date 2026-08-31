"""Création et lecture des campagnes de test."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from anomalies.catalogue import CODES, DIMENSION_PAR_CODE
from app.database import async_session_factory
from campagnes.models import STATUT_CREEE, Campagne
from campagnes.paliers import VOLUME_MAXIMUM, VOLUME_MINIMUM, palier

# Une graine tient dans un entier 32 bits signé : c'est ce que `random.Random`
# accepte partout sans surprise, et ce qu'un opérateur peut recopier à la main
# depuis un écran pour rejouer une campagne.
GRAINE_MAXIMUM = 2_147_483_647

# Nombre de références tentées avant d'abandonner. Deux créations simultanées
# peuvent viser le même numéro ; la contrainte d'unicité tranche, et on
# recommence avec le rang suivant.
TENTATIVES_REFERENCE = 5


def tirer_graine() -> int:
    """Tire une graine aléatoire, jamais nulle.

    `secrets` plutôt que `random` : la graine ne doit pas dépendre de l'état
    d'un générateur que le reste de l'application manipule, sans quoi deux
    campagnes créées à la suite pourraient hériter de valeurs voisines.
    """

    return secrets.randbelow(GRAINE_MAXIMUM) + 1


def normaliser_graine(graine: int | None) -> int:
    """Retient la graine demandée, ou en tire une."""

    if graine is None:
        return tirer_graine()
    return max(1, min(int(graine), GRAINE_MAXIMUM))


def normaliser_volume(volume: int | None, code_palier: str | None) -> int:
    """Retient le volume demandé, borné, ou celui que propose le palier."""

    propose = palier(code_palier).volume_propose
    if volume is None:
        return propose
    return max(VOLUME_MINIMUM, min(int(volume), VOLUME_MAXIMUM))


async def _prochaine_reference(session, annee: int, decalage: int = 0) -> str:
    """Construit la référence lisible de la campagne : C-2026-018.

    Le rang est recalculé à chaque appel plutôt que gardé dans un compteur :
    une séquence en base ne survivrait pas à une purge, et une campagne
    supprimée doit libérer son numéro.
    """

    debut = datetime(annee, 1, 1, tzinfo=timezone.utc)
    fin = datetime(annee + 1, 1, 1, tzinfo=timezone.utc)
    deja = await session.scalar(
        select(func.count())
        .select_from(Campagne)
        .where(Campagne.date_creation >= debut, Campagne.date_creation < fin)
    )
    return f"C-{annee}-{(deja or 0) + 1 + decalage:03d}"


def normaliser_anomalies(
    anomalies: dict[str, dict] | None
) -> dict[str, dict[str, float]]:
    """Ne retient que les types connus, avec un taux exploitable.

    Un code inconnu est écarté sans faire échouer la création : il viendrait
    d'un écran en retard sur le catalogue, et refuser toute la campagne pour
    cela ferait perdre le reste du paramétrage.
    """

    if not anomalies:
        return {}

    retenues: dict[str, dict[str, float]] = {}
    for code, reglage in anomalies.items():
        if code not in CODES:
            continue
        brut = reglage.get("taux") if isinstance(reglage, dict) else None
        if brut is None:
            continue
        taux = max(0.0, min(float(brut), 1.0))
        if taux <= 0:
            # Un type activé à 0 % n'injecte rien : le garder promettrait une
            # ligne de score qui resterait vide.
            continue
        retenues[code] = {"taux": taux}
    return retenues


def dimensions_couvertes(anomalies: dict[str, dict]) -> list[str]:
    """Les dimensions que ce réglage éprouve réellement.

    Le score final n'a de sens qu'au regard de ce périmètre : deux campagnes
    qui n'éprouvent pas les mêmes dimensions ne se comparent pas.
    """

    couvertes = {
        DIMENSION_PAR_CODE[code] for code in anomalies if code in DIMENSION_PAR_CODE
    }
    # L'ordre du catalogue, pas celui d'un ensemble, qui varie d'un appel à
    # l'autre et ferait clignoter l'affichage.
    return [
        dimension
        for dimension in dict.fromkeys(DIMENSION_PAR_CODE.values())
        if dimension in couvertes
    ]


async def creer(libelle: str | None = None, code_palier: str | None = None,
                volume_cible: int | None = None, graine: int | None = None,
                utilisateur_uuid: uuid.UUID | None = None,
                anomalies: dict[str, dict] | None = None) -> Campagne:
    """Enregistre une campagne à l'état « créée » et la retourne.

    Rien n'est encore généré : la campagne existe, avec sa graine et son
    volume visé. C'est ce qui permet de la retrouver, de la rejouer et de la
    comparer plus tard — l'unité traçable du cahier des charges.
    """

    retenu = palier(code_palier)
    reglages = normaliser_anomalies(anomalies)
    maintenant = datetime.now(timezone.utc)
    campagne = Campagne(
        campagne_id=uuid.uuid4(),
        campagne_reference="",
        campagne_libelle=(
            libelle.strip() if libelle and libelle.strip()
            else f"Campagne du {maintenant:%d/%m/%Y à %H:%M}"
        ),
        campagne_statut=STATUT_CREEE,
        campagne_graine=normaliser_graine(graine),
        campagne_palier=retenu.code,
        campagne_volume_cible=normaliser_volume(volume_cible, retenu.code),
        campagne_parametres={"anomalies": reglages},
        utilisateur_uuid=utilisateur_uuid,
        utilisateur_id_creation="campagnes",
    )

    async with async_session_factory() as session:
        for tentative in range(TENTATIVES_REFERENCE):
            campagne.campagne_reference = await _prochaine_reference(
                session, maintenant.year, tentative
            )
            session.add(campagne)
            try:
                await session.commit()
            except IntegrityError:
                # Référence déjà prise par une création concurrente : on
                # repart sur le rang suivant plutôt que de faire échouer
                # l'opérateur pour une collision de numérotation.
                await session.rollback()
                session.expunge(campagne)
                continue
            await session.refresh(campagne)
            session.expunge(campagne)
            return campagne

    raise RuntimeError(
        "Impossible d'attribuer une référence de campagne : réessayez."
    )


async def lister(limite: int = 50) -> list[Campagne]:
    """Retourne les campagnes, de la plus récente à la plus ancienne."""

    async with async_session_factory() as session:
        resultat = await session.execute(
            select(Campagne)
            .order_by(Campagne.date_creation.desc())
            .limit(limite)
        )
        return list(resultat.scalars().all())


async def lire(campagne_id: uuid.UUID) -> Campagne:
    """Retourne une campagne, ou signale qu'elle n'existe pas."""

    async with async_session_factory() as session:
        campagne = await session.get(Campagne, campagne_id)
        if campagne is None:
            raise LookupError(f"Campagne inconnue : {campagne_id}.")
        session.expunge(campagne)
        return campagne
