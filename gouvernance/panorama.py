"""Panorama de toutes les tables : colonnes, clés, volumes et propriétaire.

Le catalogue de gouvernance déclare ce qu'on veut suivre ; ce panorama regarde
ce qui est réellement en base, colonne par colonne. Les deux ne disent pas la
même chose, et c'est l'intérêt : ce qui figure ici sans figurer là est une
donnée dont personne ne répond.

Tout est lu depuis PostgreSQL au moment de l'appel — un panorama recopié à la
main serait faux dès la migration suivante.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.database import async_session_factory
from gouvernance.catalogue import CATALOGUE

# Une table du simulateur porte ce préfixe ; les tables techniques d'Alembic
# n'ont rien à faire dans un inventaire métier.
PREFIXE = "TB\\_%"


async def panorama() -> list[dict[str, Any]]:
    """Décrit chaque table : colonnes, clé primaire, clés étrangères, volume."""

    fiches = {fiche.table: fiche for fiche in CATALOGUE}
    resultat: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        tables = [ligne[0] for ligne in (await session.execute(text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename LIKE :prefixe "
            "ORDER BY tablename"
        ), {"prefixe": PREFIXE})).all()]

        colonnes_par_table = await _colonnes(session)
        cles_primaires = await _cles(session, "PRIMARY KEY")
        cles_etrangeres = await _cles(session, "FOREIGN KEY")

        for table in tables:
            fiche = fiches.get(table)
            nombre = (await session.execute(
                text(f'SELECT count(*) FROM "{table}"')
            )).scalar_one()

            resultat.append({
                "table": table,
                "lignes": nombre,
                "colonnes": colonnes_par_table.get(table, []),
                "nombre_colonnes": len(colonnes_par_table.get(table, [])),
                "cle_primaire": cles_primaires.get(table, []),
                "cles_etrangeres": cles_etrangeres.get(table, []),
                "domaine": fiche.domaine if fiche else None,
                "proprietaire": fiche.proprietaire if fiche else None,
                "criticite": fiche.criticite if fiche else None,
                "donnees_personnelles": fiche.donnees_personnelles if fiche else None,
                "au_catalogue": fiche is not None,
            })

    return resultat


async def _colonnes(session) -> dict[str, list[dict[str, Any]]]:
    """Lit les colonnes de toutes les tables en une seule requête."""

    lignes = (await session.execute(text(
        "SELECT table_name, column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name LIKE :prefixe "
        "ORDER BY table_name, ordinal_position"
    ), {"prefixe": PREFIXE})).all()

    colonnes: dict[str, list[dict[str, Any]]] = {}
    for table, colonne, type_sql, nullable in lignes:
        colonnes.setdefault(table, []).append({
            "nom": colonne,
            "type": type_sql,
            "obligatoire": nullable == "NO",
        })
    return colonnes


async def _cles(session, genre: str) -> dict[str, list[str]]:
    """Lit les colonnes portant un type de contrainte donné."""

    lignes = (await session.execute(text(
        "SELECT tc.table_name, kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        " AND tc.table_schema = kcu.table_schema "
        "WHERE tc.table_schema = 'public' AND tc.constraint_type = :genre "
        "  AND tc.table_name LIKE :prefixe "
        "ORDER BY tc.table_name, kcu.ordinal_position"
    ), {"genre": genre, "prefixe": PREFIXE})).all()

    cles: dict[str, list[str]] = {}
    for table, colonne in lignes:
        cles.setdefault(table, []).append(colonne)
    return cles


async def panorama_markdown() -> str:
    """Rend le panorama en Markdown, pour le déposer dans docs/.

    Un document engendré depuis la base ne peut pas mentir sur le schéma ;
    celui écrit à la main se périme à la première migration.
    """

    tables = await panorama()
    total_lignes = sum(table["lignes"] for table in tables)
    hors_catalogue = [table for table in tables if not table["au_catalogue"]]

    lignes = [
        "# Panorama des tables — ÉCHO",
        "",
        "Document engendré depuis la base : `GET /gouvernance/panorama`.",
        "",
        f"- Tables : **{len(tables)}**",
        f"- Lignes au total : **{total_lignes:,}**".replace(",", " "),
        f"- Tables sans propriétaire déclaré : **{len(hors_catalogue)}**",
        "",
        "## Vue d'ensemble",
        "",
        "| Table | Lignes | Colonnes | Domaine | Propriétaire | Criticité |",
        "|---|---|---|---|---|---|",
    ]
    for table in tables:
        lignes.append(
            f"| `{table['table']}` | {table['lignes']} | {table['nombre_colonnes']} "
            f"| {table['domaine'] or '—'} | {table['proprietaire'] or '—'} "
            f"| {table['criticite'] or '—'} |"
        )

    lignes += ["", "## Détail des colonnes", ""]
    for table in tables:
        lignes.append(f"### `{table['table']}`")
        lignes.append("")
        if table["cle_primaire"]:
            lignes.append(f"Clé primaire : `{'`, `'.join(table['cle_primaire'])}`")
            lignes.append("")
        lignes.append("| Colonne | Type | Obligatoire |")
        lignes.append("|---|---|---|")
        for colonne in table["colonnes"]:
            lignes.append(
                f"| `{colonne['nom']}` | {colonne['type']} "
                f"| {'oui' if colonne['obligatoire'] else 'non'} |"
            )
        lignes.append("")

    return "\n".join(lignes)
