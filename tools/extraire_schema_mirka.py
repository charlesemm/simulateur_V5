"""Lit l'export du dictionnaire Oracle de Mirka et en tire un schéma normalisé.

Les trois classeurs de schema_mirka/ sont un export de ALL_TAB_COLUMNS,
ALL_CONSTRAINTS et ALL_INDEXES. Ce script les réduit à un seul JSON, qui sert
ensuite de source unique pour générer les tables TB_SIM_* : si Mirka change, on
remplace les classeurs et on régénère, sans réécrire une ligne de schéma.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import openpyxl

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_EXPORT = RACINE / "schema_mirka"
SORTIE = DOSSIER_EXPORT / "schema_sim.json"

PREFIXE = "TB_SIM_"

# Bruit de l'export Oracle : tables techniques du Data Pump et deux tables
# applicatives de Mirka qui ne décrivent pas le métier assurance.
TABLES_IGNOREES = {
    "SYS_EXPORT_TABLE_01",
    "SYS_EXPORT_TABLE_02",
    "AA_TB_ENVIRONNEMENT",
    "AA_TB_MENU",
}

# Les agrégats statistiques sont recalculables depuis les tables de faits : le
# simulateur produit les faits, pas leurs résumés.
PREFIXES_IGNORES = ("TB_STATS_",)


def _lignes(nom_fichier: str) -> list[tuple[Any, ...]]:
    classeur = openpyxl.load_workbook(DOSSIER_EXPORT / nom_fichier, read_only=True)
    try:
        return [l for l in classeur.worksheets[0].iter_rows(min_row=2, values_only=True) if l[0]]
    finally:
        classeur.close()


def retenue(table: str) -> bool:
    """Dit si une table de Mirka a sa place dans le simulateur."""
    return table not in TABLES_IGNOREES and not table.startswith(PREFIXES_IGNORES)


def nom_sim(table: str) -> str:
    """TB_ASSURES -> TB_SIM_ASSURES, sans jamais doubler le préfixe TB_."""
    return PREFIXE + table.removeprefix("TB_")


def _entier(valeur: Any) -> int | None:
    if valeur is None or valeur == "":
        return None
    return int(valeur)


def _colonnes(valeur: Any) -> list[str]:
    """La cellule COLONNES d'une contrainte liste les colonnes, virgulées."""
    if not valeur:
        return []
    return [c.strip() for c in str(valeur).split(",") if c.strip()]


def aligner_types_fk(tables: dict[str, Any]) -> list[str]:
    """Aligne le type de chaque colonne portant une FK sur celui de sa cible.

    Oracle déclare ses NUMBER tantôt avec précision, tantôt sans : la même
    donnée métier ressort en NUMBER(10,0) d'un côté et en NUMBER nu de
    l'autre. Transposés tels quels, cela donne un INTEGER face à un NUMERIC,
    et PostgreSQL refuse la clé étrangère — à juste titre, les deux colonnes ne
    stockent pas le même ensemble de valeurs.

    On fait donc autorité sur la clé primaire référencée. La propagation est
    itérative : une FK peut viser une colonne elle-même réalignée par une
    autre FK.
    """
    alignements: list[str] = []
    for _ in range(10):
        change = False
        for fiche in tables.values():
            colonnes = {c["nom"]: c for c in fiche["colonnes"]}
            for fk in fiche["fk"]:
                cible = tables[fk["table_referencee"]]
                pk_cible = cible["pk"]
                if len(pk_cible) != len(fk["colonnes"]):
                    continue
                colonnes_cible = {c["nom"]: c for c in cible["colonnes"]}
                for source, destination in zip(fk["colonnes"], pk_cible):
                    depart, arrivee = colonnes.get(source), colonnes_cible.get(destination)
                    if depart is None or arrivee is None:
                        continue
                    forme = ("type_oracle", "longueur", "precision", "echelle")
                    if all(depart[cle] == arrivee[cle] for cle in forme):
                        continue
                    alignements.append(
                        f'{fiche["nom_sim"]}.{source} ({depart["type_oracle"]}'
                        f'{depart["precision"] or ""}) -> {cible["nom_sim"]}.{destination}'
                        f' ({arrivee["type_oracle"]}{arrivee["precision"] or ""})'
                    )
                    for cle in forme:
                        depart[cle] = arrivee[cle]
                    change = True
        if not change:
            break
    return alignements


def extraire() -> dict[str, Any]:
    tables: dict[str, dict[str, Any]] = {}

    for table, ordre, colonne, type_oracle, longueur, precision, echelle, nullable, defaut, commentaire in _lignes("COLONNES.xlsx"):
        if not retenue(table):
            continue
        fiche = tables.setdefault(
            table,
            {"nom_mirka": table, "nom_sim": nom_sim(table), "colonnes": [], "pk": [], "uniques": [], "fk": [], "index": []},
        )
        fiche["colonnes"].append(
            {
                "nom": colonne,
                "ordre": int(ordre),
                "type_oracle": type_oracle,
                "longueur": _entier(longueur),
                "precision": _entier(precision),
                "echelle": _entier(echelle),
                "nullable": nullable == "Y",
                "defaut": (str(defaut).strip() or None) if defaut else None,
                "commentaire": (str(commentaire).strip() or None) if commentaire else None,
            }
        )

    for fiche in tables.values():
        fiche["colonnes"].sort(key=lambda c: c["ordre"])

    # Les contraintes C d'Oracle sont à 99 % des NOT NULL redondants avec la
    # colonne NULLABLE : on ne garde que les vraies clauses CHECK.
    for table, nom, type_contrainte, _statut, colonnes, table_referencee, regle_suppression, condition in _lignes("CONTRAINTE.xlsx"):
        fiche = tables.get(table)
        if fiche is None:
            continue
        cols = _colonnes(colonnes)
        if type_contrainte == "P":
            fiche["pk"] = cols
        elif type_contrainte == "U":
            fiche["uniques"].append({"nom": nom, "colonnes": cols})
        elif type_contrainte == "R":
            if not retenue(table_referencee or ""):
                continue
            fiche["fk"].append(
                {
                    "nom": nom,
                    "colonnes": cols,
                    "table_referencee": table_referencee,
                    "table_referencee_sim": nom_sim(table_referencee),
                    "regle_suppression": regle_suppression,
                }
            )

    for table, nom, unicite, colonnes in _lignes("index.xlsx"):
        fiche = tables.get(table)
        if fiche is None:
            continue
        cols = _colonnes(colonnes)
        # Oracle crée un index implicite derrière chaque PK et chaque UNIQUE :
        # PostgreSQL fait de même, le redéclarer créerait un doublon.
        deja_couvert = cols == fiche["pk"] or any(cols == u["colonnes"] for u in fiche["uniques"])
        if deja_couvert:
            continue
        fiche["index"].append({"nom": nom, "colonnes": cols, "unique": unicite == "UNIQUE"})

    alignements = aligner_types_fk(tables)
    return {
        "prefixe": PREFIXE,
        "tables": dict(sorted(tables.items())),
        "alignements_fk": alignements,
    }


def main() -> None:
    schema = extraire()
    SORTIE.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    tables = schema["tables"]
    sans_pk = [t for t, f in tables.items() if not f["pk"]]
    fk_orphelines = defaultdict(list)
    for table, fiche in tables.items():
        for fk in fiche["fk"]:
            if fk["table_referencee"] not in tables:
                fk_orphelines[table].append(fk["table_referencee"])

    print(f"{len(tables)} tables retenues -> {SORTIE}")
    print(f"colonnes       : {sum(len(f['colonnes']) for f in tables.values())}")
    print(f"cles primaires : {sum(1 for f in tables.values() if f['pk'])}")
    print(f"cles etrangeres: {sum(len(f['fk']) for f in tables.values())}")
    print(f"uniques        : {sum(len(f['uniques']) for f in tables.values())}")
    print(f"index          : {sum(len(f['index']) for f in tables.values())}")
    print(f"types alignes  : {len(schema['alignements_fk'])}")
    if sans_pk:
        print(f"\nSANS CLE PRIMAIRE ({len(sans_pk)}):")
        for t in sans_pk:
            print("  ", t)
    if fk_orphelines:
        print(f"\nFK VERS UNE TABLE NON RETENUE ({sum(len(v) for v in fk_orphelines.values())}):")
        for t, cibles in fk_orphelines.items():
            print("  ", t, "->", ", ".join(cibles))


if __name__ == "__main__":
    main()
