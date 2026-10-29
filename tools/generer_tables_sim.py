"""Transforme schema_sim.json en un module de tables SQLAlchemy Core.

On génère du Core et non des modèles ORM, et sur un MetaData séparé de celui de
l'app : les 317 tables de Mirka n'ont pas à peupler Base.metadata, où elles
entreraient en collision avec les tables de l'ossature du simulateur. Le moteur
insère par Core ; les rares tables qui méritent un modèle ORM le recevront à la
main, à côté du généré.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "schema_mirka" / "schema_sim.json"
SORTIE = RACINE / "simulation" / "schema_sim" / "tables_generees.py"

# Les référentiels et tables de valeurs décrivent le monde, pas une exécution :
# ils sont partagés par toutes les simulations et ne portent pas de SIMULATION_ID.
PREFIXES_REFERENTIELS = ("TB_REF_", "TB_TV_")


# PostgreSQL tronque tout identifiant au-delà de 63 octets, et deux noms longs
# qui ne diffèrent qu'à la fin se retrouveraient confondus. On tronque donc
# nous-mêmes, en gardant un condensé du nom complet pour rester distinct.
LIMITE_IDENTIFIANT = 63


def nom_contraint(nom: str) -> str:
    if len(nom) <= LIMITE_IDENTIFIANT:
        return nom
    condense = hashlib.sha1(nom.encode()).hexdigest()[:6]
    return nom[: LIMITE_IDENTIFIANT - 7] + "_" + condense


def est_referentiel(nom_mirka: str) -> bool:
    return nom_mirka.startswith(PREFIXES_REFERENTIELS)


def type_postgres(colonne: dict[str, Any]) -> str:
    """Rend l'expression SQLAlchemy correspondant au type Oracle de la colonne."""
    oracle = colonne["type_oracle"]
    longueur, precision, echelle = colonne["longueur"], colonne["precision"], colonne["echelle"]

    if oracle == "VARCHAR2":
        return f"String({longueur})"
    if oracle == "CHAR":
        return f"CHAR({longueur})"
    if oracle == "CLOB":
        return "Text"
    if oracle in ("BLOB", "RAW"):
        return "LargeBinary"
    if oracle == "FLOAT":
        return "DOUBLE_PRECISION"
    # La DATE d'Oracle porte l'heure, et l'horloge du simulateur est avisée du
    # fuseau : tout mélange de naïf et d'avisé finit en comparaison fausse.
    if oracle.startswith("TIMESTAMP") or oracle == "DATE":
        return "DateTime(timezone=True)"
    if oracle == "NUMBER":
        if echelle:
            return f"Numeric({precision or 38}, {echelle})"
        if precision is None:
            return "Numeric"
        if precision <= 4:
            return "SmallInteger"
        if precision <= 9:
            return "Integer"
        if precision <= 18:
            return "BigInteger"
        return f"Numeric({precision}, 0)"
    raise ValueError(f"type Oracle non transposé : {oracle}")


def defaut_serveur(colonne: dict[str, Any]) -> str | None:
    """Traduit le DATA_DEFAULT d'Oracle en server_default PostgreSQL."""
    defaut = colonne["defaut"]
    if defaut is None or defaut.lower() == "null":
        return None
    if defaut.upper() == "CURRENT_TIMESTAMP":
        return "func.now()"
    # Les séquences ISEQ$$ d'Oracle sont des colonnes d'identité : PostgreSQL a
    # ses propres séquences, inutile de transporter le nom de celles de Mirka.
    if ".nextval" in defaut:
        return None
    return f'text("{defaut}")'


def rendre_colonne(colonne: dict[str, Any], dans_pk: bool) -> str:
    morceaux = [f'"{colonne["nom"]}"', type_postgres(colonne)]
    if dans_pk:
        # autoincrement=False est indispensable : sur une cle primaire d'une
        # seule colonne au type entier, le dialecte PostgreSQL de SQLAlchemy
        # emet un SERIAL, ce qui rabaisse silencieusement un NUMERIC(38,0) en
        # integer — et fait echouer les cles etrangeres qui le visent. Mirka
        # fournit ses propres cles, le simulateur insere des valeurs explicites.
        morceaux.append("primary_key=True")
        morceaux.append("autoincrement=False")
    elif not colonne["nullable"]:
        morceaux.append("nullable=False")
    defaut = defaut_serveur(colonne)
    if defaut:
        morceaux.append(f"server_default={defaut}")
    if colonne["commentaire"]:
        commentaire = colonne["commentaire"].replace('"', "'").replace("\n", " ")
        morceaux.append(f'comment="{commentaire}"')
    return "    Column(" + ", ".join(morceaux) + "),"


def rendre_table(fiche: dict[str, Any], tables: dict[str, dict[str, Any]], anomalies: list[str]) -> str:
    nom_sim, nom_mirka = fiche["nom_sim"], fiche["nom_mirka"]
    pk = set(fiche["pk"])
    lignes = [f'{nom_sim} = Table(', f'    "{nom_sim}",', "    metadonnees_sim,"]

    if not est_referentiel(nom_mirka):
        # Pas de ForeignKey ici : TB_SIMULATIONS vit sur le MetaData de l'app.
        # La contrainte est posée en base par la migration, où les deux
        # schémas coexistent, sans coupler les deux MetaData entre eux.
        #
        # Nullable, et c'est essentiel : les référentiels semés — assurés,
        # agents, droits, produits — sont créés hors de toute exécution et
        # n'ont aucun run d'origine. Les exiger rattachés rendrait le semis
        # impossible.
        lignes.append('    Column("SIMULATION_ID", PostgreSQLUUID(as_uuid=True)),')

    for colonne in fiche["colonnes"]:
        lignes.append(rendre_colonne(colonne, colonne["nom"] in pk))

    for unique in fiche["uniques"]:
        colonnes = ", ".join(f'"{c}"' for c in unique["colonnes"])
        nom_contrainte = nom_contraint(f'UQ_{nom_sim}_{"_".join(unique["colonnes"])}')
        lignes.append(f'    UniqueConstraint({colonnes}, name="{nom_contrainte}"),')

    for fk in fiche["fk"]:
        # L'export Oracle nomme la table référencée mais pas ses colonnes : la
        # cible est sa clé primaire, prise dans l'ordre déclaré.
        pk_cible = tables[fk["table_referencee"]]["pk"]
        if len(pk_cible) != len(fk["colonnes"]):
            anomalies.append(
                f'{nom_sim}.{fk["nom"]} : {len(fk["colonnes"])} colonne(s) vers'
                f' la PK de {fk["table_referencee"]} qui en compte {len(pk_cible)}'
            )
            continue
        cible = fk["table_referencee_sim"]
        colonnes = ", ".join(f'"{c}"' for c in fk["colonnes"])
        cibles = ", ".join(f'"{cible}.{c}"' for c in pk_cible)
        suppression = "CASCADE" if fk["regle_suppression"] == "CASCADE" else "NO ACTION"
        nom_contrainte = nom_contraint(f"FK_{nom_sim}_{'_'.join(fk['colonnes'])}")
        lignes.append(
            f'    ForeignKeyConstraint([{colonnes}], [{cibles}],'
            f' name="{nom_contrainte}", ondelete="{suppression}"),'
        )

    if not est_referentiel(nom_mirka):
        lignes.append(f'    Index("{nom_contraint(f"IX_{nom_sim}_SIMULATION")}", "SIMULATION_ID"),')

    for index in fiche["index"]:
        colonnes = ", ".join(f'"{c}"' for c in index["colonnes"])
        unique = ", unique=True" if index["unique"] else ""
        nom_index = nom_contraint(f'IX_{nom_sim}_{"_".join(index["colonnes"])}')
        lignes.append(f'    Index("{nom_index}", {colonnes}{unique}),')

    lignes.append(")")
    return "\n".join(lignes)


EN_TETE = '''"""Tables TB_SIM_* du simulateur, transposées du schéma Oracle de Mirka.

FICHIER GÉNÉRÉ — ne pas éditer à la main.
Régénérer avec : python tools/generer_tables_sim.py

Source : schema_mirka/schema_sim.json, lui-même extrait des classeurs
COLONNES.xlsx, CONTRAINTE.xlsx et index.xlsx par tools/extraire_schema_mirka.py.

Ces tables vivent sur leur propre MetaData, séparé du Base.metadata de l'app :
l'ossature du simulateur (TB_SIMULATIONS, TB_CAMPAGNES, TB_UTILISATEURS...) ne
doit jamais se mélanger aux tables métier reprises de Mirka.

Les tables de faits portent un SIMULATION_ID qui n'existe pas chez Mirka : il
cloisonne les lignes par exécution, ce qui rend possible la volumétrie par run
et la purge sélective. Les référentiels (TB_SIM_REF_*, TB_SIM_TV_*) décrivent le
monde et restent partagés.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CHAR,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, UUID as PostgreSQLUUID

metadonnees_sim = MetaData()
'''


def main() -> None:
    schema = json.loads(SOURCE.read_text(encoding="utf-8"))
    tables = schema["tables"]

    anomalies: list[str] = []
    blocs = [rendre_table(fiche, tables, anomalies) for fiche in tables.values()]

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(EN_TETE + "\n\n" + "\n\n".join(blocs) + "\n", encoding="utf-8")

    faits = [f["nom_sim"] for f in tables.values() if not est_referentiel(f["nom_mirka"])]
    (SORTIE.parent / "tables_de_faits.json").write_text(
        json.dumps(sorted(faits), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(tables)} tables generees -> {SORTIE}")
    if anomalies:
        print(f"CLES ETRANGERES NON TRANSPOSEES ({len(anomalies)}) :")
        for a in anomalies:
            print("  ", a)
    print(f"  dont {len(faits)} tables de faits (avec SIMULATION_ID) et {len(tables) - len(faits)} referentiels")


if __name__ == "__main__":
    main()
