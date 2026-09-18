"""Lit un fichier de campagne et rend le rapport du témoin.

Point d'entrée unique appelé par `api/routers/temoin.py` — le seul endroit où
`temoin/regles.py` touche à un fichier plutôt qu'à des lignes déjà découpées,
ce qui laisse les règles elles-mêmes testables sans écrire de CSV sur disque.
"""

from __future__ import annotations

import csv
import io

from temoin.regles import Constat, analyser

# Nom rendu dans le rapport : c'est lui que l'écran affichera comme
# « outil ayant répondu », le jour où un vrai nom d'éditeur le remplacera.
NOM_OUTIL = "Témoin ÉCHO (qualite/regles.py, rejoué sur fichier)"

# Même séparateur que campagnes/generateur.py : le témoin lit exactement ce
# que produit l'export, rien de plus.
SEPARATEUR = ";"


def analyser_fichier(contenu: bytes) -> tuple[str, list[Constat]]:
    """Décode un CSV de campagne (UTF-8) et applique les règles du témoin."""

    texte = contenu.decode("utf-8")
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=SEPARATEUR)
    lignes = list(lecteur)
    return NOM_OUTIL, analyser(lignes)
