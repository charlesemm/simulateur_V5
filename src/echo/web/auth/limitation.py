"""Freine les tentatives de connexion répétées sur un même identifiant.

Sans ce frein, rien ne limitait les essais de mot de passe sur /auth/login :
seul le coût de bcrypt ralentissait l'attaquant — et ce coût pesait sur le
serveur, dont l'unique worker cessait de répondre à tout le monde.

Le compteur vit en mémoire du processus. ÉCHO tourne sur un seul worker
uvicorn (Containerfile) : un redémarrage qui remet les compteurs à zéro est
un moindre mal qu'une dépendance de plus. Passer à plusieurs workers
demanderait de le déplacer dans un stockage partagé.

Deux compteurs, parce qu'aucun ne suffit seul :
- par identifiant saisi, qu'il existe ou non — un compte inconnu est freiné
  exactement comme un compte réel, sans quoi le 429 révélerait lesquels
  existent ;
- par adresse source, avec un seuil plus haut — il arrête celui qui essaie
  un mot de passe sur tous les comptes à la suite, sans gêner plusieurs
  agents qui partageraient une adresse.

Derrière Caddy, l'adresse source n'est la bonne que si uvicorn fait confiance
à l'en-tête X-Forwarded-For du proxy (FORWARDED_ALLOW_IPS, posé dans
deploiement/compose.prod.yaml). Sans cela, tout le monde partagerait
l'adresse de Caddy.
"""

from __future__ import annotations

import time
from collections import defaultdict

FENETRE_SECONDES = 300.0
TENTATIVES_MAXIMALES = 8
TENTATIVES_MAXIMALES_PAR_SOURCE = 30

# Au-delà, on élague les entrées périmées : un balayage d'identifiants tous
# différents ferait sinon grossir le dictionnaire sans fin.
TAILLE_AVANT_ELAGAGE = 10_000

_echecs: defaultdict[str, list[float]] = defaultdict(list)


def _recents(cle: str, maintenant: float) -> list[float]:
    """Les échecs encore dans la fenêtre, les plus anciens oubliés."""

    recents = [instant for instant in _echecs.get(cle, ()) if maintenant - instant < FENETRE_SECONDES]
    if recents:
        _echecs[cle] = recents
    else:
        _echecs.pop(cle, None)
    return recents


def _attente(cle: str, maximum: int, maintenant: float) -> int:
    recents = _recents(cle, maintenant)
    if len(recents) < maximum:
        return 0
    return int(FENETRE_SECONDES - (maintenant - recents[0])) + 1


def _cles(identifiant: str, source: str | None) -> list[tuple[str, int]]:
    cles = [(f"compte:{identifiant}", TENTATIVES_MAXIMALES)]
    if source:
        cles.append((f"source:{source}", TENTATIVES_MAXIMALES_PAR_SOURCE))
    return cles


def secondes_avant_nouvel_essai(identifiant: str, source: str | None = None) -> int:
    """Rend l'attente imposée à cet identifiant ou à cette source, 0 si libre."""

    maintenant = time.monotonic()
    return max(_attente(cle, maximum, maintenant) for cle, maximum in _cles(identifiant, source))


def enregistrer_echec(identifiant: str, source: str | None = None) -> None:
    """Compte un refus de connexion pour cet identifiant et cette source."""

    maintenant = time.monotonic()
    if len(_echecs) >= TAILLE_AVANT_ELAGAGE:
        for cle in list(_echecs):
            _recents(cle, maintenant)
    for cle, _maximum in _cles(identifiant, source):
        _echecs[cle].append(maintenant)


def oublier(identifiant: str) -> None:
    """Une connexion réussie efface l'ardoise de ce compte.

    Celle de la source reste : réussir sur son propre compte ne doit pas
    remettre à zéro les essais faits sur ceux des autres.
    """

    _echecs.pop(f"compte:{identifiant}", None)


def reinitialiser() -> None:
    """Vide tous les compteurs — pour les tests."""

    _echecs.clear()
