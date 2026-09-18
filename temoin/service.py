"""Lit un fichier de campagne et rend le rapport du témoin.

Point d'entrée unique appelé par `api/routers/temoin.py` — le seul endroit où
`temoin/regles.py` touche à un fichier plutôt qu'à des lignes déjà découpées,
ce qui laisse les règles elles-mêmes testables sans écrire de CSV sur disque.
"""

from __future__ import annotations

import csv
import io
import os
from typing import TextIO

from fastapi import UploadFile

from temoin.regles import Constat, analyser

# Nom rendu dans le rapport : c'est lui que l'écran affichera comme
# « outil ayant répondu », le jour où un vrai nom d'éditeur le remplacera.
NOM_OUTIL = "Témoin ÉCHO (qualite/regles.py, rejoué sur fichier)"

# Même séparateur que campagnes/generateur.py : le témoin lit exactement ce
# que produit l'export, rien de plus.
SEPARATEUR = ";"


# Plafond de l'envoi reçu. Un jeu d'ÉCHO pèse environ 250 octets par ligne :
# le palier « afflux » (un million de lignes) approche 240 Mio. Le défaut le
# couvre avec de la marge ; au-delà, c'est un volume que le témoin ne sait de
# toute façon pas tenir en mémoire. Le plafond borne le pire cas, il ne
# remplace pas la clé partagée qui ferme la porte aux inconnus.
TAILLE_MAXIMALE_OCTETS = int(os.getenv("ECHO_TEMOIN_TAILLE_MAX_MIO", "512")) * 1024 * 1024


class FichierRefuse(ValueError):
    """Le fichier reçu ne peut pas être analysé ; le message dit pourquoi."""


class FichierTropVolumineux(FichierRefuse):
    """Le fichier dépasse `TAILLE_MAXIMALE_OCTETS`."""


def _analyser_flux(flux: TextIO) -> tuple[str, list[Constat]]:
    """Découpe le CSV ligne à ligne et applique les règles du témoin."""

    try:
        lignes = list(csv.DictReader(flux, delimiter=SEPARATEUR))
    except UnicodeDecodeError as illisible:
        # Un CSV enregistré depuis un tableur Windows arrive souvent en
        # cp1252 : c'est une erreur de l'envoyeur, pas une panne du témoin.
        raise FichierRefuse(
            "Le fichier n'est pas encodé en UTF-8, le seul encodage que "
            "produit l'export des campagnes."
        ) from illisible
    return NOM_OUTIL, analyser(lignes)


def analyser_fichier(contenu: bytes) -> tuple[str, list[Constat]]:
    """Décode un CSV de campagne (UTF-8) et applique les règles du témoin."""

    return _analyser_flux(io.TextIOWrapper(io.BytesIO(contenu), encoding="utf-8", newline=""))


def analyser_televersement(fichier: UploadFile) -> tuple[str, list[Constat]]:
    """Analyse un fichier reçu par l'API, sans le recopier en mémoire.

    Starlette a déjà écrit l'envoi dans un fichier temporaire : on en lit la
    taille avant tout, puis on le décode en flux. L'ancien `await
    fichier.read()` chargeait tout le corps d'un coup, décodé ensuite en une
    seconde copie — un envoi assez gros faisait tomber le processus.
    """

    taille = fichier.size
    if taille is None:
        taille = fichier.file.seek(0, io.SEEK_END)
    if taille > TAILLE_MAXIMALE_OCTETS:
        raise FichierTropVolumineux(
            f"Le fichier dépasse {TAILLE_MAXIMALE_OCTETS // (1024 * 1024)} Mio, "
            "la taille maximale acceptée par le témoin."
        )

    fichier.file.seek(0)
    flux = io.TextIOWrapper(fichier.file, encoding="utf-8", newline="")
    try:
        return _analyser_flux(flux)
    finally:
        # Rendre le fichier sans le fermer : c'est Starlette qui le possède
        # et le refermera à la fin de la requête.
        flux.detach()
