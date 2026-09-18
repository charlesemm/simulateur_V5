"""Assemble le rapport de gouvernance : inventaire, lignage et conformité."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.database import async_session_factory
from gouvernance.catalogue import CATALOGUE, CRITIQUE, LIGNAGE
from gouvernance.panorama import compter_lignes
from qualite import analyser


async def _tables_reelles() -> set[str]:
    """Liste les tables métier réellement présentes en base."""

    async with async_session_factory() as session:
        lignes = (await session.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename LIKE 'TB\\_%'"
        ))).all()
    return {ligne[0] for ligne in lignes}


async def inventaire() -> dict[str, Any]:
    """Confronte le catalogue déclaré aux tables réellement en base.

    Une table présente mais absente du catalogue est une donnée que personne
    ne réclame : c'est le premier signalement qu'attend une gouvernance.
    """

    reelles = await _tables_reelles()
    declarees = {fiche.table for fiche in CATALOGUE}

    return {
        "tables_declarees": len(declarees),
        "tables_en_base": len(reelles),
        "sans_proprietaire": sorted(reelles - declarees),
        "declarees_absentes": sorted(declarees - reelles),
        "par_domaine": _compter(fiche.domaine for fiche in CATALOGUE),
        "par_criticite": _compter(fiche.criticite for fiche in CATALOGUE),
        "tables_a_donnees_personnelles": sorted(
            fiche.table for fiche in CATALOGUE if fiche.donnees_personnelles
        ),
    }


def _compter(valeurs) -> dict[str, int]:
    """Compte les occurrences, comme un GROUP BY en mémoire."""

    comptes: dict[str, int] = {}
    for valeur in valeurs:
        comptes[valeur] = comptes.get(valeur, 0) + 1
    return comptes


async def rapport(simulation_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Produit le rapport de gouvernance d'une exécution.

    Les violations de règles ne sont pas recalculées ici : ce sont celles du
    moteur de qualité, relues sous l'angle des tables et de leurs
    propriétaires. Deux comptes qui divergeraient seraient pires que pas de
    rapport du tout.
    """

    genere_le = datetime.now(timezone.utc)
    qualite = await analyser(simulation_id, inclure_referentiel=True)
    etat_inventaire = await inventaire()

    violations = [
        {
            "regle": regle["code"],
            "libelle": regle["libelle"],
            "dimension": regle["dimension"],
            "constats": regle["constats"],
        }
        for regle in qualite["regles"] if regle["constats"] > 0
    ]

    tables_critiques = [fiche.table for fiche in CATALOGUE if fiche.criticite == CRITIQUE]
    couverture = (
        100 * (etat_inventaire["tables_declarees"] / etat_inventaire["tables_en_base"])
        if etat_inventaire["tables_en_base"] else 0
    )

    return {
        "simulation_id": str(simulation_id) if simulation_id else None,
        "genere_le": genere_le.isoformat(),
        "inventaire": etat_inventaire,
        "couverture_catalogue_pourcent": round(min(couverture, 100), 1),
        "tables_critiques": tables_critiques,
        "lignage": [
            {"source": lien.source, "cible": lien.cible, "traitement": lien.traitement}
            for lien in LIGNAGE
        ],
        "violations": violations,
        "total_violations": sum(violation["constats"] for violation in violations),
    }


async def volumetrie() -> list[dict[str, Any]]:
    """Compte les lignes de chaque table du catalogue, pour la fiche de suivi."""

    reelles = await _tables_reelles()
    presentes = [fiche for fiche in CATALOGUE if fiche.table in reelles]

    async with async_session_factory() as session:
        volumes = await compter_lignes(session, [fiche.table for fiche in presentes])

    return [
        {
            "table": fiche.table,
            "domaine": fiche.domaine,
            "proprietaire": fiche.proprietaire,
            "criticite": fiche.criticite,
            "donnees_personnelles": fiche.donnees_personnelles,
            "lignes": volumes[fiche.table],
        }
        for fiche in presentes
    ]
