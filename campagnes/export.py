"""M4 — L'export du jeu piégé, dans les quatre formats du cahier.

Le fichier CSV écrit à la génération est la **source de vérité** : les trois
autres formats en dérivent, ils ne sont jamais reproduits depuis la graine.
C'est ce qui garantit qu'un XLSX et un JSON de la même campagne portent
exactement les mêmes lignes — les régénérer séparément ouvrirait la porte à
deux jeux qui divergent sans que rien ne le signale.

**Le déterminisme est la contrainte de ce module.** Le cahier demande que deux
téléchargements de la même campagne donnent deux fichiers identiques. Pour le
CSV, le JSON et le SQL, cela va de soi. Pour le XLSX, non : un classeur Excel
est une archive ZIP, et une archive porte par défaut l'heure de sa
fabrication — deux exports du même contenu produiraient des octets différents.
D'où la réécriture de l'archive à date figée, plus bas.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from campagnes.generateur import COLONNE_CAMPAGNE, COLONNE_MARQUE

# Au-delà de ce nombre de lignes, les formats dérivés sont refusés. Le CSV,
# lui, n'a pas de limite : il est renvoyé tel qu'il est sur le disque, sans
# jamais tenir en mémoire. Un XLSX d'un million de lignes, en revanche,
# épuiserait la mémoire de l'API — et le cahier interdit qu'une saturation
# ressemble à autre chose qu'à ce qu'elle est. Mieux vaut un refus qui
# s'explique qu'un processus qui tombe.
LIMITE_CONVERSION = 200_000

# Date figée pour tout ce qui, dans un XLSX, voudrait porter l'heure courante.
# 1980 n'est pas un choix esthétique : c'est la plus ancienne date que le
# format ZIP sache représenter.
DATE_ZIP = (1980, 1, 1, 0, 0, 0)

# Le nom de la table du script SQL.
TABLE_SQL = "TB_JEU_CAMPAGNE"


@dataclass(frozen=True, slots=True)
class Export:
    """Un fichier prêt à être remis : son contenu, son nom, son type."""

    contenu: bytes
    nom_fichier: str
    type_mime: str


@dataclass(frozen=True, slots=True)
class FormatExport:
    """Un format proposé à l'écran."""

    code: str
    libelle: str
    extension: str
    type_mime: str
    description: str


FORMATS: dict[str, FormatExport] = {
    "csv": FormatExport(
        code="csv",
        libelle="CSV",
        extension="csv",
        type_mime="text/csv; charset=utf-8",
        description="Le fichier tel qu'il a été produit, séparé par des points-virgules.",
    ),
    "xlsx": FormatExport(
        code="xlsx",
        libelle="Excel",
        extension="xlsx",
        type_mime=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        description="Classeur d'une feuille, pour une relecture à l'œil.",
    ),
    "json": FormatExport(
        code="json",
        libelle="JSON",
        extension="json",
        type_mime="application/json; charset=utf-8",
        description="Un objet par ligne, pour un outil qui consomme du JSON.",
    ),
    "sql": FormatExport(
        code="sql",
        libelle="Script SQL",
        extension="sql",
        type_mime="application/sql; charset=utf-8",
        description="Création de la table et insertions, à rejouer telles quelles.",
    ),
}


def formats_disponibles() -> list[FormatExport]:
    """Les formats, dans l'ordre où l'écran doit les proposer."""

    return list(FORMATS.values())


def _lire(chemin: Path) -> tuple[list[str], list[list[str]]]:
    """Relit le CSV produit et rend son en-tête et ses lignes.

    Tout est chargé en mémoire : cette fonction ne sert qu'aux formats dérivés,
    que `LIMITE_CONVERSION` borne déjà.
    """

    with chemin.open("r", newline="", encoding="utf-8") as fichier:
        lecteur = csv.reader(fichier, delimiter=";")
        lignes = list(lecteur)

    if not lignes:
        raise ValueError("Le fichier de la campagne est vide.")
    return lignes[0], lignes[1:]


# ── Le classeur, écrit à la main ────────────────────────────────────────
#
# openpyxl a été essayé et écarté. Ses classeurs ne sont pas reproductibles :
# deux exports du même contenu, dans le même processus, donnaient des octets
# différents une fois sur deux — la bibliothèque introduit un ordre qu'on ne
# peut pas fixer depuis l'extérieur. Figer les dates de l'archive ne suffisait
# donc pas.
#
# Un classeur minimal ne compte que six parties XML, toutes écrites ici. Le
# fichier obtenu est identique à l'octet près d'une exécution à l'autre, ne
# dépend d'aucune bibliothèque, et s'écrit bien plus vite qu'avec openpyxl.
# `reports/excel_generator.py` continue d'utiliser openpyxl : ses rapports
# n'ont pas à être reproductibles, et ils sont mis en forme.

_ESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# XML 1.0 n'admet pas ces caractères de contrôle, même échappés. Le jeu n'en
# porte pas encore, mais M5 doit y injecter des « caractères cassés » : autant
# que le classeur reste lisible le jour où ils arriveront. Le CSV, lui, les
# transmettra intacts — c'est là que l'anomalie doit se voir.
_CARACTERES_INTERDITS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _texte_xml(valeur: str) -> str:
    """Rend une valeur inoffensive pour du XML. L'esperluette d'abord."""

    valeur = _CARACTERES_INTERDITS.sub("", valeur)
    return (
        valeur.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _colonne_excel(index: int) -> str:
    """Le nom de colonne d'un rang : 1 → A, 26 → Z, 27 → AA."""

    lettres = ""
    while index > 0:
        index, reste = divmod(index - 1, 26)
        lettres = chr(ord("A") + reste) + lettres
    return lettres


def _feuille_xml(entete: list[str], lignes: list[list[str]]) -> bytes:
    """La feuille elle-même, une ligne de XML par ligne de données.

    Chaque cellule est déclarée `inlineStr` : le texte est écrit dans la
    cellule au lieu de renvoyer à une table de chaînes partagées. Le fichier
    est un peu plus gros, mais il n'y a plus d'index dont l'ordre pourrait
    varier — et c'est précisément ce qu'on cherche à éviter.

    Tout reste du texte, délibérément : le jeu contient des dates impossibles
    et des montants absurdes. Les typer laisserait le tableur corriger les
    pièges qu'on vient de poser.
    """

    morceaux = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{_ESPACE}"><sheetData>',
    ]
    for numero, ligne in enumerate([entete, *lignes], start=1):
        cellules = "".join(
            f'<c r="{_colonne_excel(rang)}{numero}" t="inlineStr">'
            f'<is><t xml:space="preserve">{_texte_xml(valeur)}</t></is></c>'
            for rang, valeur in enumerate(ligne, start=1)
        )
        morceaux.append(f'<row r="{numero}">{cellules}</row>')
    morceaux.append("</sheetData></worksheet>")
    return "".join(morceaux).encode("utf-8")


# Les cinq parties fixes, indépendantes du contenu.
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
    'package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
    'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/'
    'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.'
    'openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    "</Types>"
).encode("utf-8")

_RELS_RACINE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Relationships xmlns="{_RELS}">'
    f'<Relationship Id="rId1" Type="{_DOC}/officeDocument" '
    'Target="xl/workbook.xml"/>'
    "</Relationships>"
).encode("utf-8")

_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<workbook xmlns="{_ESPACE}" xmlns:r="{_DOC}">'
    '<sheets><sheet name="Jeu de test" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
).encode("utf-8")

_RELS_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Relationships xmlns="{_RELS}">'
    f'<Relationship Id="rId1" Type="{_DOC}/worksheet" '
    'Target="worksheets/sheet1.xml"/>'
    f'<Relationship Id="rId2" Type="{_DOC}/styles" Target="styles.xml"/>'
    "</Relationships>"
).encode("utf-8")

# Le strict minimum qu'Excel attend d'une feuille de styles. Les cinq blocs
# sont obligatoires même vides : sans eux, le classeur est signalé comme
# endommagé à l'ouverture.
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<styleSheet xmlns="{_ESPACE}">'
    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
    'borderId="0"/></cellStyleXfs>'
    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" '
    'xfId="0"/></cellXfs>'
    # Sans ce style nommé « Normal », les lecteurs signalent un classeur sans
    # style par défaut et en appliquent un d'office, avec un avertissement.
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/>'
    "</cellStyles>"
    "</styleSheet>"
).encode("utf-8")


def _en_xlsx(entete: list[str], lignes: list[list[str]]) -> bytes:
    """Un classeur d'une feuille, reproductible à l'octet près."""

    parties = [
        ("[Content_Types].xml", _CONTENT_TYPES),
        ("_rels/.rels", _RELS_RACINE),
        ("xl/workbook.xml", _WORKBOOK),
        ("xl/_rels/workbook.xml.rels", _RELS_WORKBOOK),
        ("xl/styles.xml", _STYLES),
        ("xl/worksheets/sheet1.xml", _feuille_xml(entete, lignes)),
    ]

    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in parties:
            # L'archive daterait sinon chaque membre de l'heure courante, ce
            # qui suffirait à faire deux fichiers différents.
            info = zipfile.ZipInfo(nom, date_time=DATE_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, contenu)
    return sortie.getvalue()


def _en_json(entete: list[str], lignes: list[list[str]]) -> bytes:
    """Un tableau d'objets, une clé par colonne.

    Les valeurs restent en texte, pour la même raison que dans le classeur :
    typer ici corrigerait les anomalies au lieu de les transmettre.
    """

    objets = [dict(zip(entete, ligne)) for ligne in lignes]
    texte = json.dumps(objets, ensure_ascii=False, indent=2)
    return (texte + "\n").encode("utf-8")


def _echapper_sql(valeur: str) -> str:
    """Met une valeur entre apostrophes, en doublant celles qu'elle contient.

    Le jeu porte des noms ivoiriens et des adresses fabriquées : une apostrophe
    y est parfaitement possible, et couperait le script en deux.
    """

    return "'" + valeur.replace("'", "''") + "'"


def _identifiant_sql(nom: str) -> str:
    """Met un nom de colonne entre guillemets, en doublant ceux qu'il contient.

    Pendant que `_echapper_sql` protège les valeurs, celle-ci protège les noms :
    l'en-tête du CSV n'est pas plus digne de confiance qu'une cellule, et le
    script produit ici est joué sur la base de quelqu'un d'autre.
    """

    return '"' + nom.replace('"', '""') + '"'


def _en_sql(entete: list[str], lignes: list[list[str]], reference: str) -> bytes:
    """Un script de création et d'insertion, rejouable tel quel.

    **Toutes les colonnes sont en TEXT**, y compris les dates et les montants.
    Ce n'est pas de la paresse : le jeu contient des dates impossibles et des
    quantités nulles là où le métier les interdit. Une colonne DATE refuserait
    justement les lignes qui font tout l'intérêt du test, et le script
    échouerait sur les anomalies au lieu de les livrer.
    """

    morceaux: list[str] = [
        f"-- Jeu de test ECHO — campagne {reference}",
        "-- DONNEES FICTIVES : ne jamais charger dans une base de production.",
        "--",
        "-- Toutes les colonnes sont en TEXT : le jeu contient volontairement",
        "-- des valeurs qu'un type strict rejetterait, et qui sont l'objet même",
        "-- du test.",
        "",
        f"CREATE TABLE IF NOT EXISTS {TABLE_SQL} (",
    ]
    morceaux.append(",\n".join(f"    {_identifiant_sql(colonne)} TEXT" for colonne in entete))
    morceaux.append(");")
    morceaux.append("")

    colonnes = ", ".join(_identifiant_sql(colonne) for colonne in entete)
    for ligne in lignes:
        valeurs = ", ".join(_echapper_sql(cellule) for cellule in ligne)
        morceaux.append(f"INSERT INTO {TABLE_SQL} ({colonnes}) VALUES ({valeurs});")

    return ("\n".join(morceaux) + "\n").encode("utf-8")


def exporter(chemin: Path, code_format: str, reference: str) -> Export:
    """Rend le jeu d'une campagne dans le format demandé.

    Le marquage n'est jamais retiré : il est déjà dans le CSV source, et aucun
    des convertisseurs ne le distingue des autres colonnes. Il n'y a donc pas
    d'option pour s'en passer — c'est ce que le cahier appelle « non
    désactivable ».
    """

    format_demande = FORMATS.get(code_format)
    if format_demande is None:
        connus = ", ".join(FORMATS)
        raise ValueError(f"Format inconnu : {code_format}. Attendus : {connus}.")

    if not chemin.exists():
        raise FileNotFoundError(
            "Le jeu de cette campagne n'est pas sur le disque : il faut le "
            "générer avant de pouvoir le télécharger."
        )

    nom_fichier = f"{reference}_jeu.{format_demande.extension}"

    # Le CSV part tel quel. C'est le seul format qui ne passe pas par la
    # mémoire, et donc le seul qui tienne sur les gros paliers.
    if code_format == "csv":
        return Export(
            contenu=chemin.read_bytes(),
            nom_fichier=nom_fichier,
            type_mime=format_demande.type_mime,
        )

    entete, lignes = _lire(chemin)
    if len(lignes) > LIMITE_CONVERSION:
        # Les milliers sont séparés à part : appliquer le remplacement à la
        # phrase entière emporterait aussi ses virgules de ponctuation.
        compte = f"{len(lignes):,}".replace(",", " ")
        plafond = f"{LIMITE_CONVERSION:,}".replace(",", " ")
        raise ValueError(
            f"Ce jeu compte {compte} lignes, au-delà des {plafond} que la "
            f"conversion en {format_demande.libelle} sait tenir en mémoire. "
            "Le format CSV, lui, reste disponible sans limite."
        )

    if code_format == "xlsx":
        contenu = _en_xlsx(entete, lignes)
    elif code_format == "json":
        contenu = _en_json(entete, lignes)
    else:
        contenu = _en_sql(entete, lignes, reference)

    return Export(
        contenu=contenu,
        nom_fichier=nom_fichier,
        type_mime=format_demande.type_mime,
    )


def verifier_marquage(chemin: Path) -> bool:
    """Dit si le fichier porte bien ses deux colonnes de marquage.

    Sert au test de recette et à la garde de l'API : un jeu produit avant M4
    n'a pas de marquage, et le livrer sans le dire serait exactement ce que le
    chapitre 4 cherche à empêcher.
    """

    if not chemin.exists():
        return False
    with chemin.open("r", newline="", encoding="utf-8") as fichier:
        premiere = fichier.readline().strip()
    colonnes = premiere.split(";")
    return colonnes[:2] == [COLONNE_MARQUE, COLONNE_CAMPAGNE]
