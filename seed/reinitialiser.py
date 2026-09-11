"""Vide les tables d'opération et le contenu des référentiels, avant un seed neuf.

Pourquoi : le 11/09/2026, les codes des référentiels (centres, agents,
professionnels, médicaments…) ont changé de format. Ce sont des clés
primaires : relancer le seed ajouterait les nouvelles lignes à côté des
anciennes au lieu de les remplacer. Il faut donc repartir de tables vides.

Ce qui est gardé : les comptes utilisateurs, les campagnes (avec leurs
échanges et leurs corrigés), le catalogue et le réglage des anomalies, et la
version Alembic.

    python -m seed.reinitialiser              # dit ce qui serait vidé, sans rien toucher
    python -m seed.reinitialiser --confirmer  # vide réellement
    python -m seed                            # puis recharge les référentiels

Tout est lu dans la base elle-même — la liste des tables comme leurs clés
étrangères — et non dans les modèles : aucun module métier n'est chargé, et
une table créée par une seule migration n'est pas oubliée.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.database import async_session_factory

CONSERVEES = frozenset({
    "alembic_version",
    "TB_UTILISATEURS",
    "TB_CAMPAGNES", "TB_CAMPAGNES_ECHANGES", "TB_CAMPAGNES_CORRIGE",
    "TB_REF_ANOMALIES", "TB_CONFIG_ANOMALIES",
})


async def tables_a_vider(session) -> list[str]:
    """Toutes les tables présentes en base, moins celles qu'on garde."""

    lignes = await session.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
    ))
    return sorted(nom for (nom,) in lignes if nom not in CONSERVEES)


async def verifier_conservees(session, a_vider: set[str]) -> None:
    """Refuse de continuer si une table gardée pointe vers une table vidée.

    Le TRUNCATE part sans CASCADE, Postgres refuserait donc de toute façon ;
    autant le dire avant, avec le nom des deux tables.
    """

    liens = await session.execute(text(
        "SELECT source.relname, cible.relname FROM pg_constraint contrainte "
        "JOIN pg_class source ON source.oid = contrainte.conrelid "
        "JOIN pg_class cible ON cible.oid = contrainte.confrelid "
        "WHERE contrainte.contype = 'f'"
    ))
    for source, cible in liens:
        if source in CONSERVEES and cible in a_vider:
            raise RuntimeError(
                f"{source} est gardée mais pointe vers {cible}, qui serait "
                "vidée : ajoutez l'une à la liste de l'autre avant de continuer."
            )


async def reinitialiser(confirmer: bool) -> list[str]:
    async with async_session_factory() as session:
        tables = await tables_a_vider(session)
        await verifier_conservees(session, set(tables))
        if confirmer and tables:
            liste = ", ".join(f'"{nom}"' for nom in tables)
            await session.execute(text(f"TRUNCATE TABLE {liste} RESTART IDENTITY"))
            await session.commit()
    return tables


def main() -> None:
    parseur = argparse.ArgumentParser(
        description="Vide les tables d'opération et les référentiels avant un seed neuf.")
    parseur.add_argument("--confirmer", action="store_true",
                         help="vide réellement ; sans cette option, rien n'est touché")
    arguments = parseur.parse_args()

    tables = asyncio.run(reinitialiser(arguments.confirmer))
    gardees = ", ".join(sorted(CONSERVEES - {"alembic_version"}))
    if arguments.confirmer:
        print(f"{len(tables)} tables vidées. Gardées : {gardees}.")
        print("Relancez maintenant le seed : python -m seed")
    else:
        print(f"{len(tables)} tables seraient vidées :")
        for nom in tables:
            print(f"  - {nom}")
        print(f"Gardées : {gardees}.")
        print("Rien n'a été touché. Relancez avec --confirmer pour vider.")


if __name__ == "__main__":
    main()
