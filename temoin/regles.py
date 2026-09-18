"""Les règles du témoin : ce qu'il sait repérer dans un jeu de campagne.

Elles rejouent, à l'échelle d'une ligne de fichier, ce que `qualite/regles.py`
vérifie en base pour le moteur temps réel — mais ici tout part d'un
`csv.DictReader`, jamais d'une requête SQL : le témoin lit exactement ce
qu'un vrai outil recevrait, rien d'autre.

Chaque règle rend un couple (champ, motif) en texte libre plutôt qu'un code
d'anomalie du catalogue : un vrai outil ne connaîtra jamais le vocabulaire
interne d'ÉCHO, et le rapprochement de M7 doit pouvoir fonctionner sur
« ligne + champ » seuls, sans exiger que l'outil devine nos noms de code.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from campagnes.generateur import (
    CHAMPS_IDENTITE, CHAMPS_OBLIGATOIRES, CHARGES_INJECTION, COLONNE_CAMPAGNE,
    COLONNE_MARQUE,
)
from seed.constants import HEALTH_CENTER_TYPES, MEDICAL_ACTS

# Au-delà, un montant ne peut plus correspondre à un acte réel — même seuil
# que qualite/regles.py, pour que témoin et moteur jugent pareil.
SEUIL_MONTANT_DEMESURE = Decimal("1000000")

# En pourcentage (100/70), pas une fraction — même échelle que
# REGIME_TAUX et PRESTATION_TAUX_REMBOURSEMENT sur la vraie base.
TAUX_PAR_REGIME = {"RAM": Decimal("100"), "RGB": Decimal("70")}

CHAMPS_DATE_ATTENDUS = (
    "FACTURE_DATE_SOINS", "FACTURE_DATE_EMISSION",
    "ASSURE_DATE_NAISSANCE", "DROITS_DATE_DEBUT", "DROITS_DATE_FIN",
)

CODES_ACTES = frozenset(code for code, *_ in MEDICAL_ACTS)
CODES_TYPE_CENTRE = frozenset(code for code, _ in HEALTH_CENTER_TYPES)

# Colonnes techniques, jamais du contenu métier : les règles de texte
# (caractères cassés, tentative d'injection) ne les regardent pas.
COLONNES_HORS_CONTENU = frozenset({COLONNE_MARQUE, COLONNE_CAMPAGNE, "LIGNE_ID"})


@dataclass(frozen=True, slots=True)
class Constat:
    """Un constat du témoin : la ligne, le champ s'il y en a un, et le motif."""

    ligne: int
    champ: str | None
    type: str


def _decimal(valeur: str | None) -> Decimal | None:
    if not valeur:
        return None
    try:
        return Decimal(valeur)
    except InvalidOperation:
        return None


def _date_iso(valeur: str | None) -> date | None:
    """Une date ISO simple (`2026-01-03`) ou complète, avec heure et fuseau
    (`2025-01-01T00:00:00+00:00`) — les droits sont horodatés comme
    DateTime(timezone=True) sur la vraie base (TB_ASSURES_DROITS), les autres
    dates restent nues. Les deux formats doivent passer par la même règle.
    """

    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(valeur).date()
    except ValueError:
        return None


def _ressemble_a_une_date(valeur: str) -> bool:
    """Vrai pour un texte qui a la forme d'une date, sans être au format ISO."""

    if not valeur or _date_iso(valeur) is not None:
        return False
    return bool(re.match(r"^\d{1,4}[./-]\d{1,2}[./-]\d{1,4}$", valeur))


def _texte_suspect(valeur: str) -> bool:
    """Un point d'interrogation posé à la place d'un caractère, ou du mojibake."""

    if not valeur:
        return False
    if "?" in valeur:
        return True
    return bool(re.search(r"Ã.|Â.", valeur))


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _repliee(texte: str) -> str:
    """Une forme aplatie d'un nom, pour rapprocher un doublon approchant."""

    return _sans_accents(texte).upper().replace("-", " ").replace("'", " ")


def _numero_ligne(ligne: dict[str, str]) -> int:
    try:
        return int(ligne.get("LIGNE_ID") or 0)
    except ValueError:
        return 0


# ── Règles portant sur une seule ligne ───────────────────────────────────

def _montant(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    montant = _decimal(ligne.get("PRESTATION_MONTANT_DEPENSE"))
    if montant is not None and (montant < 0 or montant > SEUIL_MONTANT_DEMESURE):
        yield Constat(numero, "PRESTATION_MONTANT_DEPENSE", "Montant hors norme")


def _taux(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    attendu = TAUX_PAR_REGIME.get(ligne.get("REGIME_CODE", ""))
    taux = _decimal(ligne.get("PRESTATION_TAUX_REMBOURSEMENT"))
    if attendu is not None and taux is not None and taux != attendu:
        yield Constat(numero, "PRESTATION_TAUX_REMBOURSEMENT",
                      "Taux de remboursement étranger au régime")


def _naissance(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    naissance = _date_iso(ligne.get("ASSURE_DATE_NAISSANCE"))
    if naissance is None:
        return
    if naissance > date.today() or (date.today() - naissance).days > 120 * 365:
        yield Constat(numero, "ASSURE_DATE_NAISSANCE", "Date de naissance impossible")


def _dates_de_soins(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    soins = _date_iso(ligne.get("FACTURE_DATE_SOINS"))
    if soins is None:
        return
    debut = _date_iso(ligne.get("DROITS_DATE_DEBUT"))
    fin = _date_iso(ligne.get("DROITS_DATE_FIN"))
    if debut is not None and fin is not None and not (debut <= soins <= fin):
        yield Constat(numero, "FACTURE_DATE_SOINS",
                      "Date de soins hors de la période de droits")
        return
    emission = _date_iso(ligne.get("FACTURE_DATE_EMISSION"))
    if emission is not None and soins > emission:
        yield Constat(numero, "FACTURE_DATE_SOINS",
                      "Date de soins postérieure à la facture")


def _formats_de_date(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    for champ in CHAMPS_DATE_ATTENDUS:
        valeur = ligne.get(champ, "")
        if valeur and _date_iso(valeur) is None and _ressemble_a_une_date(valeur):
            yield Constat(numero, champ, "Date écrite dans un format inattendu")


def _quantites(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    prescrite = _decimal(ligne.get("PRESTATION_QUANTITE_PRESCRITE"))
    servie = _decimal(ligne.get("PRESTATION_QUANTITE_SERVIE"))
    if prescrite is None or servie is None:
        return
    if servie > prescrite:
        yield Constat(numero, "PRESTATION_QUANTITE_SERVIE",
                      "Quantité servie supérieure à la prescrite")
    elif servie == 0 and prescrite > 0:
        yield Constat(numero, "PRESTATION_QUANTITE_SERVIE",
                      "Quantité servie nulle malgré une prescription")


def _identifiant(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    valeur = ligne.get("ASSURE_NUMERO_IDENTIFIANT", "")
    if not re.match(r"^CMU\d{10}$", valeur):
        yield Constat(numero, "ASSURE_NUMERO_IDENTIFIANT",
                      "Identifiant assuré mal formé")


def _numero_secu(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    """Même règle que `qualite/regles.py:_numero_secu_invalide`, côté fichier :
    un numéro qui n'a pas 13 ou 14 chiffres, ou la sentinelle du moteur temps
    réel (`00000000000000`) — un numéro qui ne peut appartenir à personne.
    """

    valeur = ligne.get("NUMERO_SECU", "")
    if not re.match(r"^\d{13,14}$", valeur) or valeur == "00000000000000":
        yield Constat(numero, "NUMERO_SECU",
                      "Numéro de sécurité sociale mal formé")


def _email(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    valeur = ligne.get("AGENT_EMAIL", "")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", valeur):
        yield Constat(numero, "AGENT_EMAIL", "Adresse électronique mal formée")


def _referentiels(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    type_centre = ligne.get("CENTRE_SANTE_TYPE_CODE", "")
    if type_centre and type_centre not in CODES_TYPE_CENTRE:
        yield Constat(numero, "CENTRE_SANTE_TYPE_CODE",
                      "Type d'établissement hors référentiel")

    prestation = ligne.get("PRESTATION_CODE", "")
    if (prestation and prestation not in CODES_ACTES
            and not prestation.startswith(("CONS-", "DENT-"))):
        yield Constat(numero, "PRESTATION_CODE", "Code de prestation hors référentiel")


def _champs_obligatoires(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    for champ in CHAMPS_OBLIGATOIRES:
        if not (ligne.get(champ) or "").strip():
            yield Constat(numero, champ, "Champ obligatoire vide")


def _texte(ligne: dict[str, str], numero: int) -> Iterable[Constat]:
    for champ, valeur in ligne.items():
        if champ in COLONNES_HORS_CONTENU or not isinstance(valeur, str):
            continue
        if _texte_suspect(valeur):
            yield Constat(numero, champ, "Caractères cassés à la lecture")
        if valeur in CHARGES_INJECTION:
            yield Constat(numero, champ, "Tentative d'injection détectée")


REGLES_PAR_LIGNE = (
    _montant, _taux, _naissance, _dates_de_soins, _formats_de_date,
    _quantites, _identifiant, _numero_secu, _email, _referentiels,
    _champs_obligatoires, _texte,
)


def _constats_de_la_ligne(ligne: dict[str, str]) -> list[Constat]:
    numero = _numero_ligne(ligne)
    constats: list[Constat] = []
    for regle in REGLES_PAR_LIGNE:
        constats.extend(regle(ligne, numero))
    return constats


# ── Doublons : la seule règle qui regarde plusieurs lignes à la fois ──────

def _identite_stricte(ligne: dict[str, str]) -> tuple[str, ...]:
    return tuple(ligne.get(champ, "") for champ in CHAMPS_IDENTITE)


def _identite_approchee(ligne: dict[str, str]) -> tuple[str, str, str]:
    return (
        _repliee(ligne.get("ASSURE_NOM", "")),
        ligne.get("ASSURE_PRENOMS", ""),
        ligne.get("ASSURE_DATE_NAISSANCE", ""),
    )


def _doublons(lignes: list[dict[str, str]]) -> list[Constat]:
    """Deux fiches déjà vues : identité stricte d'abord, puis approchée.

    Aucune fenêtre glissante ici, contrairement au générateur : le témoin
    relit le fichier entier d'un coup, il n'a pas la contrainte de mémoire
    d'un flux qui s'écrit ligne à ligne.
    """

    constats: list[Constat] = []
    vues_strictes: set[tuple[str, ...]] = set()
    vues_approchees: set[tuple[str, str, str]] = set()

    for ligne in lignes:
        numero = _numero_ligne(ligne)
        stricte = _identite_stricte(ligne)
        approchee = _identite_approchee(ligne)

        if stricte in vues_strictes:
            constats.append(Constat(numero, "ASSURE_NUMERO_IDENTIFIANT",
                                     "Doublon strict d'une fiche déjà vue"))
        elif approchee in vues_approchees:
            constats.append(Constat(numero, "ASSURE_NOM",
                                     "Doublon approchant d'une fiche déjà vue"))

        vues_strictes.add(stricte)
        vues_approchees.add(approchee)

    return constats


def analyser(lignes: list[dict[str, str]]) -> list[Constat]:
    """Applique toutes les règles du témoin à un jeu de campagne complet."""

    constats: list[Constat] = []
    for ligne in lignes:
        constats.extend(_constats_de_la_ligne(ligne))
    constats.extend(_doublons(lignes))
    return constats
