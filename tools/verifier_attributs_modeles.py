"""Confronte le code aux modèles générés, sans rien exécuter.

La bascule vers le schéma de Mirka n'a cassé aucun import : les classes gardent
leurs noms. Elle a cassé des **attributs** — une colonne qui n'existe plus, un
nom que Mirka écrit autrement. Ces ruptures ne se voient qu'à l'exécution, donc
au mieux dans un test, au pire en production.

Ce script les trouve par analyse de l'arbre syntaxique. Il relève deux formes :

- `Invoice(facture_numero=..., ...)` — un argument nommé qui ne correspond à
  aucune colonne,
- `Invoice.facture_numero` — un attribut de classe inexistant.

Il ne voit pas les accès sur une instance (`facture.numero`), dont le type ne
se déduit pas sans inférence. Ce qu'il rend est donc un plancher, pas un
inventaire complet.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from sqlalchemy.orm import configure_mappers

import echo.web.app.models as modeles

RACINE = Path(__file__).resolve().parent.parent

# Dossiers sans intérêt : dépendances, anciennes migrations, code généré.
IGNORES = {".venv", "versions_archive", "__pycache__", "node_modules", "dashboard", "tools"}


def attributs_connus() -> dict[str, set[str]]:
    """Pour chaque modèle, l'ensemble de ses attributs mappés."""
    configure_mappers()
    connus: dict[str, set[str]] = {}
    for nom in dir(modeles):
        classe = getattr(modeles, nom)
        table = getattr(classe, "__table__", None)
        if table is None:
            continue
        noms = {c.key for c in classe.__mapper__.column_attrs}
        noms |= {r.key for r in classe.__mapper__.relationships}
        connus[nom] = noms
    return connus


def fichiers_python() -> list[Path]:
    return [
        chemin
        for chemin in RACINE.rglob("*.py")
        if not IGNORES & set(chemin.relative_to(RACINE).parts)
    ]


def analyser(chemin: Path, connus: dict[str, set[str]]) -> list[str]:
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    relatif = chemin.relative_to(RACINE).as_posix()
    trouvailles: list[str] = []

    for noeud in ast.walk(arbre):
        # Invoice(facture_numero=...) : argument nommé inconnu du modèle.
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
            attendus = connus.get(noeud.func.id)
            if attendus is not None:
                for argument in noeud.keywords:
                    if argument.arg and argument.arg not in attendus:
                        trouvailles.append(
                            f"{relatif}:{noeud.lineno}  {noeud.func.id}({argument.arg}=...)"
                        )
        # Invoice.facture_numero : attribut de classe inexistant.
        elif isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name):
            attendus = connus.get(noeud.value.id)
            if attendus is not None and noeud.attr not in attendus:
                # Les attributs offerts par SQLAlchemy ou Python ne sont pas des
                # colonnes et ne sont pas en cause.
                if not noeud.attr.startswith("__") and not hasattr(
                    getattr(modeles, noeud.value.id), noeud.attr
                ):
                    trouvailles.append(f"{relatif}:{noeud.lineno}  {noeud.value.id}.{noeud.attr}")

    return trouvailles


def main() -> int:
    connus = attributs_connus()
    par_fichier: dict[str, list[str]] = {}
    for chemin in fichiers_python():
        for trouvaille in analyser(chemin, connus):
            par_fichier.setdefault(trouvaille.split(":")[0], []).append(trouvaille)

    total = sum(len(v) for v in par_fichier.values())
    print(f"{len(connus)} modeles inspectes, {total} ruptures d'attribut dans {len(par_fichier)} fichiers\n")
    for fichier in sorted(par_fichier, key=lambda f: -len(par_fichier[f])):
        trouvailles = par_fichier[fichier]
        print(f"{len(trouvailles):4d}  {fichier}")
        for trouvaille in sorted(set(trouvailles))[:60]:
            print(f"        {trouvaille.split('  ', 1)[1]}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
