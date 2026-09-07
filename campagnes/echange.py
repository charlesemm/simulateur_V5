"""M6 — Le canal API : transmet le jeu d'une campagne à l'outil testé.

Le contrat tient en deux phrases. ÉCHO envoie le fichier de la campagne en
partie jointe (`multipart/form-data`, champ « fichier ») avec sa référence.
L'outil rend un objet JSON `{"constats": [{"ligne", "champ", "type"}, ...]}` —
la liste peut être vide, mais la clé doit y être : c'est elle qui distingue
« rien détecté » d'« aucun détail rendu ».

Trois pannes sont distinguées, jamais confondues avec un score de 0 % :
- **silence** — l'outil ne répond pas (connexion refusée, delai dépassé,
  statut HTTP autre que 200) ;
- **rapport_malforme** — la réponse n'est pas un JSON exploitable, ou son
  contenu ne respecte pas la forme attendue ;
- **rapport_sans_detail** — la réponse est un JSON valide, mais sans la clé
  « constats » : l'outil a répondu, sans le détail que M7 exige.

En attendant le vrai outil, l'adresse par défaut pointe vers le témoin
(`api/routers/temoin.py`), qui répond exactement à ce contrat.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.database import async_session_factory
from campagnes.models import (
    MOTIF_RAPPORT_MALFORME, MOTIF_RAPPORT_SANS_DETAIL, MOTIF_SILENCE,
    RESULTAT_ECHEC, RESULTAT_SUCCES, STATUT_ECHEC_ECHANGE, STATUT_RAPPORT_RECU,
    Campagne, EchangeCampagne,
)

logger = logging.getLogger(__name__)

# Adresse par défaut : le témoin, sur le serveur qui héberge ÉCHO lui-même.
# La faire pointer ailleurs — variable d'environnement, ou adresse donnée à
# la transmission — est justement ce qui permettra de brancher le vrai outil
# testé le jour venu, sans retoucher ce module.
ADRESSE_PAR_DEFAUT = os.getenv(
    "ADRESSE_OUTIL_TESTE", "http://127.0.0.1:8000/temoin/analyser"
)

DELAI_ATTENTE_SECONDES = 30.0


def _horodatage() -> datetime:
    return datetime.now(timezone.utc)


def _classer_rapport(corps: Any) -> tuple[str | None, list[dict], str | None]:
    """Distingue les deux pannes qui tiennent dans le corps d'une réponse 200.

    Rend `(motif_echec, constats, message)` ; `motif_echec` vaut `None`
    quand le rapport est exploitable.
    """

    if not isinstance(corps, dict):
        return (MOTIF_RAPPORT_MALFORME, [],
                "Le corps de la réponse n'est pas un objet JSON.")

    if "constats" not in corps:
        # Un résumé sans détail n'est pas un défaut de format : l'outil a
        # répondu correctement, il n'a simplement pas rendu ce que le
        # contrat exige. Confondre ceci avec un score de 0 % est exactement
        # ce que le cahier interdit (chapitre M6).
        return (MOTIF_RAPPORT_SANS_DETAIL, [],
                "La réponse ne porte pas de détail ligne par ligne.")

    constats = corps["constats"]
    if not isinstance(constats, list):
        return MOTIF_RAPPORT_MALFORME, [], "« constats » n'est pas une liste."

    valides: list[dict] = []
    for entree in constats:
        if not isinstance(entree, dict) or not isinstance(entree.get("ligne"), int):
            return (MOTIF_RAPPORT_MALFORME, [],
                    "Une entrée du rapport ne porte pas de numéro de ligne.")
        valides.append(entree)

    return None, valides, None


async def transmettre(
    campagne_id: UUID, adresse: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> EchangeCampagne:
    """Envoie le jeu d'une campagne à l'outil testé, et note ce qui en revient.

    `client` ne sert qu'aux tests : ils y glissent un client attaché
    directement à l'application (`httpx.ASGITransport`), pour faire tourner
    le témoin en boucle fermée sans ouvrir de port. En usage réel, un client
    HTTP ordinaire part sur le réseau vers l'adresse configurée.
    """

    async with async_session_factory() as session:
        campagne = await session.get(Campagne, campagne_id)
        if campagne is None:
            raise LookupError(f"Campagne inconnue : {campagne_id}.")
        if not campagne.campagne_fichier:
            raise RuntimeError(
                "Cette campagne n'a pas encore été générée : rien à transmettre."
            )
        chemin = Path(campagne.campagne_fichier)
        reference = campagne.campagne_reference

    try:
        contenu = chemin.read_bytes()
    except OSError as absent:
        raise RuntimeError(
            f"Le fichier de la campagne est introuvable sur le disque : {absent}."
        ) from absent

    cible = adresse or ADRESSE_PAR_DEFAUT
    echange = EchangeCampagne(
        echange_id=uuid.uuid4(),
        campagne_id=campagne_id,
        echange_adresse=cible,
        echange_date_envoi=_horodatage(),
        echange_resultat=RESULTAT_ECHEC,
        echange_motif_echec=MOTIF_SILENCE,
        utilisateur_id_creation="campagnes",
    )

    propre = client is None
    http_client = client or httpx.AsyncClient(timeout=DELAI_ATTENTE_SECONDES)
    try:
        try:
            reponse = await http_client.post(
                cible,
                files={"fichier": (chemin.name, contenu, "text/csv")},
                data={"campagne_reference": reference},
            )
        except httpx.HTTPError as panne:
            echange.echange_message = str(panne)
        else:
            echange.echange_date_reception = _horodatage()
            if reponse.status_code != 200:
                echange.echange_message = (
                    f"Réponse HTTP {reponse.status_code} de l'outil testé."
                )
            else:
                try:
                    corps = reponse.json()
                except (ValueError, json.JSONDecodeError):
                    echange.echange_motif_echec = MOTIF_RAPPORT_MALFORME
                    echange.echange_message = "La réponse n'est pas un JSON valide."
                else:
                    motif, constats, message = _classer_rapport(corps)
                    if motif is None:
                        echange.echange_resultat = RESULTAT_SUCCES
                        echange.echange_motif_echec = None
                        echange.echange_nombre_constats = len(constats)
                        echange.echange_rapport = corps
                        echange.echange_message = None
                    else:
                        echange.echange_motif_echec = motif
                        echange.echange_message = message
    finally:
        if propre:
            await http_client.aclose()

    if echange.echange_resultat != RESULTAT_SUCCES:
        logger.info("Échange en échec pour la campagne %s : %s (%s)",
                    campagne_id, echange.echange_motif_echec, echange.echange_message)

    nouveau_statut = (
        STATUT_RAPPORT_RECU if echange.echange_resultat == RESULTAT_SUCCES
        else STATUT_ECHEC_ECHANGE
    )
    async with async_session_factory() as session:
        session.add(echange)
        campagne = await session.get(Campagne, campagne_id)
        if campagne is not None:
            campagne.campagne_statut = nouveau_statut
        await session.commit()
        await session.refresh(echange)
        session.expunge(echange)
    return echange


async def historique(campagne_id: UUID) -> list[EchangeCampagne]:
    """Tous les envois d'une campagne, du plus récent au plus ancien."""

    async with async_session_factory() as session:
        resultat = await session.execute(
            select(EchangeCampagne)
            .where(EchangeCampagne.campagne_id == campagne_id)
            .order_by(EchangeCampagne.echange_date_envoi.desc())
        )
        return list(resultat.scalars().all())
