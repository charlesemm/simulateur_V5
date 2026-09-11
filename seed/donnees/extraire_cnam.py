"""Extrait les listes publiques de la CNAM vers les CSV que lit le seed.

Le seed ne va jamais sur Internet : il lit les trois fichiers posés à côté de
ce script. Ce script-ci sert à les régénérer quand la CNAM met ses pages à
jour ; il n'utilise que la bibliothèque standard.

    python -m seed.donnees.extraire_cnam            # télécharge les pages
    python -m seed.donnees.extraire_cnam --local D  # relit des pages déjà
                                                     # enregistrées dans D

Sources (pages publiques, consultées le 11/09/2026) :
- https://ipscnam.ci/hopitaux-pharmacies-cmu/           -> établissements, pharmacies
- https://ipscnam.ci/medicaments-diabete-cmu/           -> spécialités avec prix
- https://ipscnam.ci/medicaments-hypertension-arterielle-cmu/
- https://ipscnam.ci/autres-medicaments/                -> spécialités sans prix
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent

PAGES = {
    "hopitaux-pharmacies-cmu": "https://ipscnam.ci/hopitaux-pharmacies-cmu/",
    "medicaments-diabete-cmu": "https://ipscnam.ci/medicaments-diabete-cmu/",
    "medicaments-hypertension-arterielle-cmu":
        "https://ipscnam.ci/medicaments-hypertension-arterielle-cmu/",
    "autres-medicaments": "https://ipscnam.ci/autres-medicaments/",
}

# Le type d'établissement n'est pas publié : il se lit dans le nom. L'ordre
# compte, du plus précis au plus général (« CENTRE DE SANTE URBAIN » avant
# « CENTRE DE SANTE »). Les codes sont ceux de seed.constants.HEALTH_CENTER_TYPES.
# Les motifs tolèrent les coquilles présentes dans la source (« CENTREDE
# SANTE », « CENTRE DE SNTE », « DIPENSAIRE », « DISPESNAIRE »…).
REGLES_TYPE = (
    ("CHU", r"CENTRE HOSPITALIER UNIVERSITAIRE|^CHU\b"),
    ("CHR", r"CENTRE HOSPITALIER REGIONAL|^CHR\b"),
    ("HG", r"HOPITAL GENERAL|^HG\b"),
    ("CAT", r"ANTI[- ]?TUBERCULEUX"),
    ("INST", r"^INSTITUT"),
    ("MIL", r"ARMEES|MILITAIRE|GENDARMERIE|POLICE|GARDE REPUBLICAINE|SAPEURS"
            r"|FORCES SPECIALES|^CSA\b"),
    ("SSSU", r"SSSU|SANTE SCOLAIRE"),
    ("PMI", r"^PMI\b|PROTECTION MATERNELLE"),
    ("MAT", r"^MATERNITE"),
    ("CSU", r"CENTRE ?(DE )?S\w*NTE URBAIN|^CSU\b"),
    ("CSR", r"CENTRE ?(DE )?S\w*NTE RURAL|^CSR\b"),
    ("DISP", r"DI[SP]\w*AIRE"),
    ("FSU", r"FORMATION SANITAIRE"),
    ("CMS", r"MEDICO[- ]?SOCIAL|SOCIO[- ]?MEDICAL|MEDICO[- ]?CHIRU|CENTRE MEDICAL"
            r"|SERVICE MEDICAL|HOTEL MEDICAL|INFIRMERIE|CREMOSS|ACTION SOCIALE|^SOTRA\b"),
    ("CLN", r"CLINIQUE"),
    ("HOP", r"HOPITAL"),
    ("CS", r"^CENTRE ?(DE )?S\w*NTE"),
)
TYPE_PAR_DEFAUT = "AUT"


class _Tableaux(HTMLParser):
    """Relève chaque tableau de la page, ligne par ligne, cellule par cellule."""

    def __init__(self) -> None:
        super().__init__()
        self.tableaux: list[list[list[str]]] = []
        self._lignes: list[list[str]] | None = None
        self._ligne: list[str] | None = None
        self._cellule: list[str] | None = None

    def handle_starttag(self, balise, attributs):
        if balise == "table":
            self._lignes = []
        elif balise == "tr" and self._lignes is not None:
            self._ligne = []
        elif balise in ("td", "th") and self._ligne is not None:
            self._cellule = []
        elif balise == "br" and self._cellule is not None:
            self._cellule.append("\n")

    def handle_endtag(self, balise):
        if balise in ("td", "th") and self._cellule is not None:
            self._ligne.append("".join(self._cellule).strip())
            self._cellule = None
        elif balise == "tr" and self._ligne is not None:
            if any(self._ligne):
                self._lignes.append(self._ligne)
            self._ligne = None
        elif balise == "table" and self._lignes is not None:
            self.tableaux.append(self._lignes)
            self._lignes = None

    def handle_data(self, donnees):
        if self._cellule is not None:
            self._cellule.append(donnees)


def _tableaux(html: str) -> list[list[list[str]]]:
    analyseur = _Tableaux()
    analyseur.feed(html)
    return analyseur.tableaux


def _propre(texte: str) -> str:
    """Espaces normalisés, apostrophes et tirets recollés : un nom, une forme."""

    texte = re.sub(r"\s*'\s*", "'", texte.replace("’", "'"))
    texte = re.sub(r"\s*-\s*", "-", texte)
    return re.sub(r"\s+", " ", texte).strip(" -.•\t")


def _cle(texte: str) -> str:
    """Forme de comparaison : majuscules sans accents."""

    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").upper()


def type_etablissement(denomination: str) -> str:
    cle = _cle(denomination)
    return next((code for code, motif in REGLES_TYPE if re.search(motif, cle)),
                TYPE_PAR_DEFAUT)


def _elements(cellule: str) -> list[str]:
    """Une cellule liste plusieurs noms séparés par des retours à la ligne."""

    return [nom for nom in (_propre(morceau) for morceau in cellule.split("\n")) if nom]


def extraire_etablissements(html: str) -> tuple[list[dict], list[dict]]:
    """Établissements et pharmacies, dédoublonnés par (localité, nom)."""

    etablissements: dict[tuple[str, str], dict] = {}
    pharmacies: dict[tuple[str, str], dict] = {}
    for tableau in _tableaux(html):
        for ligne in tableau:
            if len(ligne) < 3 or _cle(ligne[0]).startswith("LOCALITE"):
                continue
            localite = _propre(ligne[0]).upper()
            for nom in _elements(ligne[1]):
                if "AUCUN" in _cle(nom):
                    continue
                etablissements.setdefault((_cle(localite), _cle(nom)), {
                    "localite": localite, "denomination": nom,
                    "type_code": type_etablissement(nom),
                })
            for nom in _elements(ligne[2]):
                if "AUCUN" in _cle(nom):
                    continue
                pharmacies.setdefault((_cle(localite), _cle(nom)), {
                    "localite": localite, "denomination": nom,
                })
    return ([etablissements[cle] for cle in sorted(etablissements)],
            [pharmacies[cle] for cle in sorted(pharmacies)])


def _prix(texte: str) -> str:
    """« 4,132.59 » -> « 4132.59 » ; vide si la cellule ne porte pas de prix."""

    texte = texte.replace(",", "").replace(" ", "")
    return texte if re.fullmatch(r"\d+(\.\d+)?", texte) else ""


def _dci_depuis_entete(entete: str) -> str:
    """« ATORVASTATINE 10 MG COMPRIME » -> « ATORVASTATINE » : tout avant le dosage."""

    correspondance = re.match(r"^(.*?)\s+\d", entete)
    return _propre(correspondance.group(1) if correspondance else entete)


def extraire_medicaments_avec_prix(html: str, liste: str) -> list[dict]:
    """Pages diabète et hypertension : une ligne d'en-tête par DCI, puis ses
    spécialités numérotées avec leur prix."""

    lignes, dci = [], ""
    for tableau in _tableaux(html):
        for ligne in tableau:
            if len(ligne) < 3:
                continue
            numero, libelle, prix = (_propre(cellule) for cellule in ligne[:3])
            if not numero and libelle and not _prix(prix):
                if not _cle(libelle).startswith("FORMULATION"):
                    dci = _dci_depuis_entete(libelle)
                continue
            if numero.isdigit() and libelle:
                lignes.append({"dci": dci, "libelle": libelle,
                               "prix_fcfa": _prix(prix), "liste": liste})
    return lignes


def extraire_autres_medicaments(html: str) -> list[dict]:
    """Page « autres » : numéro, DCI, libellé — aucun prix publié."""

    lignes = []
    for tableau in _tableaux(html):
        for ligne in tableau:
            if len(ligne) < 3 or not _propre(ligne[0]).isdigit():
                continue
            lignes.append({"dci": _propre(ligne[1]), "libelle": _propre(ligne[2]),
                           "prix_fcfa": "", "liste": "autres"})
    return lignes


def _lire(nom: str, local: Path | None) -> str:
    if local is not None:
        return (local / f"{nom}.html").read_text(encoding="utf-8", errors="replace")
    requete = urllib.request.Request(PAGES[nom], headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        return reponse.read().decode("utf-8", errors="replace")


def _ecrire(nom: str, lignes: list[dict], colonnes: list[str]) -> None:
    with (DOSSIER / nom).open("w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=colonnes, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"{nom} : {len(lignes)} lignes")


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--local", type=Path, help="dossier des pages déjà téléchargées")
    arguments = parseur.parse_args()

    etablissements, pharmacies = extraire_etablissements(
        _lire("hopitaux-pharmacies-cmu", arguments.local))
    medicaments = (
        extraire_medicaments_avec_prix(_lire("medicaments-diabete-cmu", arguments.local), "diabete")
        + extraire_medicaments_avec_prix(
            _lire("medicaments-hypertension-arterielle-cmu", arguments.local), "hypertension")
        + extraire_autres_medicaments(_lire("autres-medicaments", arguments.local))
    )

    _ecrire("etablissements_cnam.csv", etablissements, ["localite", "denomination", "type_code"])
    _ecrire("pharmacies_cnam.csv", pharmacies, ["localite", "denomination"])
    _ecrire("medicaments_cmu.csv", medicaments, ["dci", "libelle", "prix_fcfa", "liste"])


if __name__ == "__main__":
    main()
