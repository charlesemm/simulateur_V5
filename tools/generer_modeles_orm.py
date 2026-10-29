"""Génère les modèles ORM du simulateur depuis le schéma de Mirka.

Le module `simulation/schema_sim/` décrit les 317 tables de Mirka en
SQLAlchemy Core. Mais le code du simulateur travaille en ORM, et seules une
trentaine de ces tables l'intéressent : celles que le moteur écrit et que
l'API relit. Ce script produit, pour ce sous-ensemble, de vrais modèles
déclaratifs posés sur le `Base` de l'application.

Les noms de classes viennent de `app/models/correspondances.py` et sont ceux
d'avant la bascule : les vingt modules qui importent `Invoice` ou
`InsuredPerson` gardent leurs imports. Ce qui change, c'est la table visée et
ses colonnes.

Ce que ce script ne fait pas : les relations (`relationship`). Leurs noms
d'attributs — `invoices`, `insured_person`, `rights` — ont été choisis à la
main et ne se déduisent pas du schéma. Elles sont donc ajoutées à la main dans
`app/models/relations.py`, à mesure que le code en a besoin.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

# Chargé par chemin, et non par import de paquet : `import app.models`
# exécute `app/models/__init__.py`, qui importe le module que ce script
# génère. Un module à demi généré rendrait le générateur inutilisable.
_specification = importlib.util.spec_from_file_location(
    "correspondances", Path(__file__).resolve().parent.parent / "src" / "echo" / "web" / "app" / "models" / "correspondances.py"
)
_correspondances = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(_correspondances)

CLES_LOGIQUES = _correspondances.CLES_LOGIQUES
CORRESPONDANCES = _correspondances.CORRESPONDANCES
table_de = _correspondances.table_de

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "schema_mirka" / "schema_sim.json"
SORTIE = RACINE / "src" / "echo" / "web" / "app" / "models" / "mirka.py"

# Ces quatre colonnes existent sur presque toutes les tables de Mirka, et
# AuditMixin les déclare déjà : les redéclarer ferait doublon.
COLONNES_AUDIT = {
    "DATE_CREATION",
    "UTILISATEUR_ID_CREATION",
    "DATE_MODIFICATION",
    "UTILISATEUR_ID_MODIFICATION",
}

# SimulationScopedMixin déclare SIMULATION_ID : même raison.
COLONNE_CLOISONNEMENT = "SIMULATION_ID"

PREFIXES_REFERENTIELS = ("REF_", "TV_")


def est_referentiel(table_mirka: str) -> bool:
    return table_mirka.startswith(PREFIXES_REFERENTIELS)


def attribut(colonne: str) -> str:
    """PERSONNE_UUID -> personne_uuid."""
    return colonne.lower()


def _type_et_annotation(colonne: dict[str, Any]) -> tuple[str, str]:
    """Rend le type SQLAlchemy et l'annotation Python d'une colonne."""
    oracle = colonne["type_oracle"]
    longueur, precision, echelle = colonne["longueur"], colonne["precision"], colonne["echelle"]

    if oracle == "VARCHAR2":
        return f"String({longueur})", "str"
    if oracle == "CHAR":
        return f"CHAR({longueur})", "str"
    if oracle == "CLOB":
        return "Text", "str"
    if oracle in ("BLOB", "RAW"):
        return "LargeBinary", "bytes"
    if oracle == "FLOAT":
        return "DOUBLE_PRECISION", "float"
    if oracle.startswith("TIMESTAMP") or oracle == "DATE":
        return "DateTime(timezone=True)", "datetime"
    if oracle == "NUMBER":
        if echelle:
            return f"Numeric({precision or 38}, {echelle})", "Decimal"
        if precision is None:
            return "Numeric", "Decimal"
        if precision <= 4:
            return "SmallInteger", "int"
        if precision <= 9:
            return "Integer", "int"
        if precision <= 18:
            return "BigInteger", "int"
        return f"Numeric({precision}, 0)", "Decimal"
    raise ValueError(f"type Oracle non transposé : {oracle}")


def defaut_serveur(colonne: dict[str, Any]) -> str | None:
    """Traduit le DATA_DEFAULT d'Oracle en server_default PostgreSQL.

    Sans cela, l'ORM ignore une valeur que la base sait poser : une colonne
    obligatoire à défaut CURRENT_TIMESTAMP partait à NULL et l'insertion
    échouait, alors que le DDL l'aurait remplie.
    """
    defaut = colonne["defaut"]
    if defaut is None or defaut.lower() == "null":
        return None
    if defaut.upper() == "CURRENT_TIMESTAMP":
        return "func.now()"
    # Les sequences ISEQ$$ d'Oracle sont des colonnes d'identite : PostgreSQL a
    # les siennes, le nom de celles de Mirka ne se transporte pas.
    if ".nextval" in defaut:
        return None
    return f'text("{defaut}")'


def rendre_colonne(colonne: dict[str, Any], dans_pk: bool, fk: str | None) -> str:
    type_sql, annotation = _type_et_annotation(colonne)
    optionnel = not dans_pk and colonne["nullable"]
    if optionnel:
        annotation += " | None"

    # L'ordre compte : mapped_column attend le nom, puis le type, et seulement
    # ensuite les éléments de schéma comme ForeignKey.
    arguments = [f'"{colonne["nom"]}"', type_sql]
    if fk:
        arguments.append(f'ForeignKey("{fk}")')
    if dans_pk:
        # Sans autoincrement=False, le dialecte PostgreSQL transforme une clé
        # primaire entière d'une seule colonne en SERIAL, ce qui change son
        # type en base et fait échouer les clés étrangères qui la visent.
        arguments.append("primary_key=True")
        arguments.append("autoincrement=False")
    elif not colonne["nullable"]:
        arguments.append("nullable=False")
    defaut = defaut_serveur(colonne)
    if defaut:
        arguments.append(f"server_default={defaut}")

    ligne = f'    {attribut(colonne["nom"])}: Mapped[{annotation}] = mapped_column('
    corps = ", ".join(arguments)
    if len(ligne) + len(corps) + 1 <= 100:
        return ligne + corps + ")"
    return ligne + "\n        " + ",\n        ".join(arguments) + ",\n    )"


def rendre_classe(classe: str, fiche: dict[str, Any], sous_ensemble: dict[str, str]) -> str:
    table_mirka = CORRESPONDANCES[classe]
    # Quelques tables de Mirka n'ont pas de clé primaire déclarée. L'ORM en
    # exige une : on prend alors la clé logique de correspondances.py, posée
    # sur le mapper et non en base.
    cle_logique = CLES_LOGIQUES.get(classe)
    pk = set(fiche["pk"] or cle_logique or [])

    # AuditMixin déclare les quatre colonnes d'audit d'un bloc : on ne s'en sert
    # que si Mirka les porte toutes. Quelques tables n'en ont qu'une partie, et
    # le mixin leur ajouterait des colonnes absentes de la base.
    presentes = {c["nom"] for c in fiche["colonnes"]}
    audit_complet = COLONNES_AUDIT <= presentes

    # Une table de faits est cloisonnée par exécution ; un référentiel décrit le
    # monde et reste partagé entre toutes les simulations.
    bases = ["Base"]
    if audit_complet:
        bases.insert(0, "AuditMixin")
    if not est_referentiel(table_mirka):
        bases.insert(0, "SimulationScopedMixin")
    mixins = ", ".join(bases)

    # Les clés étrangères ne sont posées que vers les tables du sous-ensemble :
    # viser une table absente du Base ferait échouer la configuration des
    # mappers. Celles de Mirka vers le reste du schéma existent en base, posées
    # par la migration socle.
    cibles: dict[str, str] = {}
    for contrainte in fiche["fk"]:
        cible_sim = contrainte["table_referencee_sim"]
        if cible_sim not in sous_ensemble.values():
            continue
        colonnes_cibles = _pk_de(sous_ensemble, cible_sim)
        if len(colonnes_cibles) != len(contrainte["colonnes"]):
            continue
        for source, destination in zip(contrainte["colonnes"], colonnes_cibles):
            cibles[source] = f"{cible_sim}.{destination}"

    lignes = [
        f"class {classe}({mixins}):",
        f'    """{_docstring(classe, table_mirka)}"""',
        "",
        f'    __tablename__ = "{table_de(classe)}"',
        "",
    ]
    if not fiche["pk"] and cle_logique:
        # SQLAlchemy resout ces noms contre les attributs Python, en
        # minuscules, et non contre les colonnes SQL.
        colonnes = ", ".join(f'"{attribut(c)}"' for c in cle_logique)
        lignes[-1:] = [
            "    # Mirka ne declare pas de cle primaire sur cette table. Cette",
            "    # identite ne vaut que pour l'ORM : rien n'est ajoute en base.",
            f"    __mapper_args__ = {{\"primary_key\": [{colonnes}]}}",
            "",
        ]
    for colonne in fiche["colonnes"]:
        if colonne["nom"] == COLONNE_CLOISONNEMENT:
            continue
        if audit_complet and colonne["nom"] in COLONNES_AUDIT:
            continue
        lignes.append(rendre_colonne(colonne, colonne["nom"] in pk, cibles.get(colonne["nom"])))

    return "\n".join(lignes)


def _pk_de(sous_ensemble: dict[str, str], table_sim: str) -> list[str]:
    for classe, table in sous_ensemble.items():
        if table == table_sim:
            return _FICHES[classe]["pk"]
    return []


def _docstring(classe: str, table_mirka: str) -> str:
    quoi = "Référentiel" if est_referentiel(table_mirka) else "Table de faits"
    return f"{quoi} Mirka TB_{table_mirka}, transposé pour le simulateur."


_FICHES: dict[str, dict[str, Any]] = {}


EN_TETE = '''"""Modèles ORM du simulateur, posés sur le schéma de Mirka.

FICHIER GÉNÉRÉ — ne pas éditer à la main.
Régénérer avec : python tools/generer_modeles_orm.py

La correspondance entre ces classes et les tables de Mirka est déclarée dans
`app/models/correspondances.py`, qui en explique aussi les six arbitrages.

Les noms de classes sont ceux d'avant la bascule vers le schéma de Mirka : le
code qui importe `Invoice` ou `InsuredPerson` n'a pas eu à changer d'import.
Leurs colonnes, en revanche, sont celles de Mirka.

Les relations (`relationship`) ne sont pas générées : leurs noms d'attributs
ont été choisis à la main et ne se déduisent pas du schéma. Elles vivent dans
`app/models/relations.py`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column

from echo.web.app.models.base import AuditMixin, Base, SimulationScopedMixin
'''


def main() -> None:
    schema = json.loads(SOURCE.read_text(encoding="utf-8"))
    par_nom_sim = {f["nom_sim"]: f for f in schema["tables"].values()}

    sous_ensemble = {classe: table_de(classe) for classe in CORRESPONDANCES}
    for classe, table_sim in sous_ensemble.items():
        _FICHES[classe] = par_nom_sim[table_sim]

    blocs = [rendre_classe(classe, _FICHES[classe], sous_ensemble) for classe in CORRESPONDANCES]

    SORTIE.write_text(EN_TETE + "\n\n" + "\n\n\n".join(blocs) + "\n", encoding="utf-8")

    colonnes = sum(
        1
        for fiche in _FICHES.values()
        for c in fiche["colonnes"]
        if c["nom"] not in COLONNES_AUDIT and c["nom"] != COLONNE_CLOISONNEMENT
    )
    faits = sum(1 for classe in CORRESPONDANCES if not est_referentiel(CORRESPONDANCES[classe]))
    print(f"{len(blocs)} modeles generes -> {SORTIE}")
    print(f"  {colonnes} colonnes, {faits} tables de faits, {len(blocs) - faits} referentiels")


if __name__ == "__main__":
    main()
