"""Canal de commande vers un moteur déjà lancé.

Jusqu'ici, une fois `start()` parti, seule la vitesse pouvait encore changer :
rien ne permettait d'armer une anomalie ou de déclencher un aléa en pleine
exécution. Ce canal comble ce trou. Les ordres sont déposés par l'API et
consommés par le moteur entre deux passages, ce qui évite de toucher à l'état
partagé depuis le fil de la requête HTTP.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Ordres reconnus par le moteur.
ARMER_ANOMALIE = "armer_anomalie"
DESARMER_ANOMALIE = "desarmer_anomalie"
DECLENCHER_ALEA = "declencher_alea"

ORDRES = (ARMER_ANOMALIE, DESARMER_ANOMALIE, DECLENCHER_ALEA)


@dataclass(frozen=True, slots=True)
class Commande:
    """Un ordre adressé au moteur, avec ses arguments."""

    ordre: str
    cible: str
    parametres: dict[str, Any] = field(default_factory=dict)


class CanalDeCommande:
    """File d'ordres en attente, vidée par le moteur au fil de sa boucle."""

    def __init__(self, taille_maximale: int = 200) -> None:
        self._file: asyncio.Queue[Commande] = asyncio.Queue(maxsize=taille_maximale)

    def deposer(self, commande: Commande) -> bool:
        """Dépose un ordre sans attendre, et dit s'il a été accepté.

        Le refus est volontairement silencieux côté moteur : une file pleine
        signale un opérateur qui empile les ordres plus vite que le moteur ne
        les traite, pas une erreur du moteur.
        """

        try:
            self._file.put_nowait(commande)
        except asyncio.QueueFull:
            logger.warning("Canal de commande saturé : ordre %s ignoré.", commande.ordre)
            return False
        return True

    def vider(self) -> list[Commande]:
        """Retire et retourne tous les ordres en attente, sans bloquer."""

        commandes: list[Commande] = []
        while True:
            try:
                commandes.append(self._file.get_nowait())
            except asyncio.QueueEmpty:
                return commandes

    def en_attente(self) -> int:
        """Nombre d'ordres déposés que le moteur n'a pas encore lus."""

        return self._file.qsize()
