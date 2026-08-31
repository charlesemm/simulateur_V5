"""M3 — Le générateur de jeux de données piégés, et son corrigé.

Ce générateur n'est pas le moteur de simulation, et c'est délibéré. Le moteur
temps réel est concurrent, daté sur l'horloge réelle et tire une partie de son
hasard côté PostgreSQL : deux exécutions de même graine ne produiraient jamais
le même fichier. Ici, tout descend d'un seul `random.Random(graine)`, dans un
ordre fixe, sans horloge et sans base — c'est ce qui rend le fichier
reproductible à l'octet près, comme l'exige le chapitre 3 du cahier.

Trois règles à ne jamais enfreindre sous peine de perdre la rejouabilité :

1. **Aucun appel à l'horloge** dans les données produites. Une date « du jour »
   changerait le fichier d'un jour à l'autre pour la même graine.
2. **Aucune lecture de la base** pour composer une ligne : le contenu d'une
   table évolue, le fichier suivrait.
3. **Un ordre de parcours fixe** — celui du catalogue — pour tirer les
   anomalies. Parcourir un dictionnaire de réglages laisserait l'ordre de
   saisie de l'opérateur décider du fichier.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from anomalies.catalogue import (
    CODES, DATE_ANTIDATEE, DATE_HORS_DROITS, DATE_NAISSANCE_ABERRANTE,
    DATE_SOINS_FUTURE, EMAIL_INVALIDE, MONTANT_ABERRANT, MONTANT_HORS_BAREME,
    NUMERO_SECU_INVALIDE, PRESTATION_ORPHELINE, QUANTITE_EXCESSIVE,
    QUANTITE_NULLE, REPARTITION_FAUSSEE, TYPE_CENTRE_INCONNU,
)
from seed.constants import (
    HEALTH_CENTER_TYPES, IVORIAN_CITIES, IVORIAN_FIRST_NAMES,
    IVORIAN_LAST_NAMES, MEDICAL_ACTS,
)

logger = logging.getLogger(__name__)

# Où sont déposés les jeux produits. Un dossier à part des rapports : ces
# fichiers ont une autre durée de vie et une autre raison d'être.
DOSSIER_JEUX = Path("campagnes/output")

# Date d'ancrage du jeu produit. **Constante, jamais « aujourd'hui »** : c'est
# ce qui permet à une campagne rejouée dans six mois de produire exactement le
# même fichier qu'aujourd'hui.
DATE_REFERENCE = date(2026, 1, 1)

# Étendue des dates de soins autour de la référence, en jours.
AMPLITUDE_JOURS = 180

# Les colonnes du jeu, dans l'ordre. Elles couvrent exactement ce que les
# treize types d'anomalies savent corrompre : changer cette liste change le
# fichier, donc l'empreinte, donc la comparaison entre deux campagnes.
COLONNES = (
    "LIGNE_ID",
    "NUMERO_IMMATRICULATION",
    "ASSURE_NOM",
    "ASSURE_PRENOMS",
    "ASSURE_DATE_NAISSANCE",
    "AGENT_EMAIL",
    "REGIME_CODE",
    "DROITS_DATE_DEBUT",
    "DROITS_DATE_FIN",
    "FACTURE_NUMERO",
    "FACTURE_DATE_EMISSION",
    "FACTURE_DATE_SOINS",
    "CENTRE_SANTE_CODE",
    "CENTRE_SANTE_TYPE_CODE",
    "PRESTATION_CODE",
    "PRESTATION_QUANTITE_PRESCRITE",
    "PRESTATION_QUANTITE_SERVIE",
    "PRESTATION_MONTANT_DEPENSE",
    "PRESTATION_TAUX_REMBOURSEMENT",
    "PRESTATION_MONTANT_CMU",
    "PRESTATION_MONTANT_ASSURE",
)

# Taux de prise en charge par régime : le RAM (assistance médicale) couvre
# tout, le RGB laisse un ticket modérateur de 30 %.
TAUX_PAR_REGIME = {"RAM": Decimal("1.00"), "RGB": Decimal("0.70")}

TYPES_CENTRE = tuple(code for code, _ in HEALTH_CENTER_TYPES)
CODES_ACTES = tuple(code for code, *_ in MEDICAL_ACTS)
MONTANTS_ACTES = {code: Decimal(str(montant)) for code, *_, montant in MEDICAL_ACTS}

# Lignes écrites entre deux mises à jour de la progression. Rafraîchir à chaque
# ligne coûterait plus cher que de produire la ligne elle-même.
PAS_PROGRESSION = 250

# Corrigés accumulés avant d'être versés en base, pour ne pas garder un million
# de lignes en mémoire sur les gros paliers.
TAILLE_LOT_CORRIGE = 5_000


@dataclass(slots=True)
class Constat:
    """Une anomalie posée : la ligne, le champ, et les deux valeurs.

    C'est l'unité du corrigé. Le rapprochement du chapitre 2 s'y adosse : sans
    la ligne **et** le champ, aucun rapport d'outil testé ne peut être
    confronté à autre chose qu'un total.
    """

    ligne: int
    champ: str
    anomalie_code: str
    valeur_origine: str
    valeur_injectee: str


def _formater(valeur: Any) -> str:
    """Rend une valeur en texte, de façon stable d'une exécution à l'autre.

    Le formatage fait partie du contrat de reproductibilité : un montant écrit
    tantôt `5000` tantôt `5000.00` produirait deux fichiers différents pour la
    même graine.
    """

    if isinstance(valeur, Decimal):
        return f"{valeur:.2f}"
    if isinstance(valeur, date):
        return valeur.isoformat()
    return str(valeur)


def _immatriculation(rng: random.Random) -> str:
    """Un numéro d'immatriculation à treize chiffres, comme le veut la CMU."""

    return "".join(str(rng.randint(0, 9)) for _ in range(13))


def ligne_saine(rng: random.Random, numero: int) -> dict[str, Any]:
    """Compose une ligne cohérente, avant toute corruption.

    L'ordre des tirages compte autant que leur nombre : ajouter un tirage au
    milieu de cette fonction décale tous les suivants et change l'intégralité
    du fichier à graine constante.
    """

    nom = rng.choice(IVORIAN_LAST_NAMES)
    prenom = rng.choice(IVORIAN_FIRST_NAMES)
    regime = rng.choice(("RAM", "RGB"))

    naissance = DATE_REFERENCE - timedelta(days=rng.randint(6_570, 25_550))
    debut_droits = DATE_REFERENCE - timedelta(days=rng.randint(200, 900))
    fin_droits = debut_droits + timedelta(days=rng.choice((365, 730, 1095)))

    date_soins = DATE_REFERENCE - timedelta(days=rng.randint(0, AMPLITUDE_JOURS))
    date_emission = date_soins + timedelta(days=rng.randint(0, 5))

    code_acte = rng.choice(CODES_ACTES)
    quantite = rng.randint(1, 4)
    montant = MONTANTS_ACTES[code_acte] * quantite
    taux = TAUX_PAR_REGIME[regime]
    part_cmu = (montant * taux).quantize(Decimal("0.01"))

    return {
        "LIGNE_ID": numero,
        "NUMERO_IMMATRICULATION": _immatriculation(rng),
        "ASSURE_NOM": nom,
        "ASSURE_PRENOMS": prenom,
        "ASSURE_DATE_NAISSANCE": naissance,
        "AGENT_EMAIL": (
            f"{prenom.lower().replace(' ', '.')}."
            f"{nom.lower().replace(chr(39), '')}@cnam.ci"
        ),
        "REGIME_CODE": regime,
        "DROITS_DATE_DEBUT": debut_droits,
        "DROITS_DATE_FIN": fin_droits,
        "FACTURE_NUMERO": f"F-{numero:09d}",
        "FACTURE_DATE_EMISSION": date_emission,
        "FACTURE_DATE_SOINS": date_soins,
        "CENTRE_SANTE_CODE": f"CI-CMU-{rng.randint(1, 250):05d}",
        "CENTRE_SANTE_TYPE_CODE": rng.choice(TYPES_CENTRE),
        "PRESTATION_CODE": code_acte,
        "PRESTATION_QUANTITE_PRESCRITE": quantite,
        "PRESTATION_QUANTITE_SERVIE": quantite,
        "PRESTATION_MONTANT_DEPENSE": montant,
        "PRESTATION_TAUX_REMBOURSEMENT": taux,
        "PRESTATION_MONTANT_CMU": part_cmu,
        "PRESTATION_MONTANT_ASSURE": (montant - part_cmu).quantize(Decimal("0.01")),
        # Colonne technique, hors du fichier : la ville sert à donner un code
        # de centre plausible sans multiplier les tirages.
        "_VILLE": rng.choice(IVORIAN_CITIES),
    }


# ── Les injecteurs ───────────────────────────────────────────────────────
#
# Chacun corrompt un champ et rend le couple (valeur d'origine, valeur posée).
# Ils sont écrits ici plutôt que repris d'`anomalies/config.py` : ceux du
# moteur tirent sur leur propre générateur et journalisent en base, deux
# choses qui casseraient la reproductibilité du fichier.

Injecteur = Callable[[random.Random, dict[str, Any]], tuple[str, Any, Any]]


def _montant_aberrant(rng, ligne):
    origine = ligne["PRESTATION_MONTANT_DEPENSE"]
    if rng.random() < 0.5:
        injectee = -origine
    else:
        injectee = origine * Decimal(rng.randint(1_000, 50_000))
    ligne["PRESTATION_MONTANT_DEPENSE"] = injectee
    return "PRESTATION_MONTANT_DEPENSE", origine, injectee


def _taux_hors_bareme(rng, ligne):
    origine = ligne["PRESTATION_TAUX_REMBOURSEMENT"]
    # Un taux étranger au régime : 100 % pour un RGB, ou une valeur qui
    # n'existe dans aucun barème.
    injectee = Decimal("1.00") if origine != Decimal("1.00") else Decimal("0.42")
    ligne["PRESTATION_TAUX_REMBOURSEMENT"] = injectee
    return "PRESTATION_TAUX_REMBOURSEMENT", origine, injectee


def _date_naissance_aberrante(rng, ligne):
    origine = ligne["ASSURE_DATE_NAISSANCE"]
    if rng.random() < 0.5:
        injectee = DATE_REFERENCE + timedelta(days=rng.randint(1, 3_650))
    else:
        injectee = date(1850 + rng.randint(0, 30), 1, 1)
    ligne["ASSURE_DATE_NAISSANCE"] = injectee
    return "ASSURE_DATE_NAISSANCE", origine, injectee


def _date_antidatee(rng, ligne):
    origine = ligne["FACTURE_DATE_SOINS"]
    injectee = origine - timedelta(days=rng.randint(400, 3_000))
    ligne["FACTURE_DATE_SOINS"] = injectee
    return "FACTURE_DATE_SOINS", origine, injectee


def _date_soins_future(rng, ligne):
    origine = ligne["FACTURE_DATE_SOINS"]
    injectee = ligne["FACTURE_DATE_EMISSION"] + timedelta(days=rng.randint(1, 120))
    ligne["FACTURE_DATE_SOINS"] = injectee
    return "FACTURE_DATE_SOINS", origine, injectee


def _date_hors_droits(rng, ligne):
    origine = ligne["FACTURE_DATE_SOINS"]
    injectee = ligne["DROITS_DATE_FIN"] + timedelta(days=rng.randint(1, 400))
    ligne["FACTURE_DATE_SOINS"] = injectee
    return "FACTURE_DATE_SOINS", origine, injectee


def _repartition_faussee(rng, ligne):
    origine = ligne["PRESTATION_MONTANT_ASSURE"]
    injectee = (origine + Decimal(rng.randint(500, 5_000))).quantize(Decimal("0.01"))
    ligne["PRESTATION_MONTANT_ASSURE"] = injectee
    return "PRESTATION_MONTANT_ASSURE", origine, injectee


def _quantite_excessive(rng, ligne):
    origine = ligne["PRESTATION_QUANTITE_SERVIE"]
    injectee = origine + rng.randint(1, 20)
    ligne["PRESTATION_QUANTITE_SERVIE"] = injectee
    return "PRESTATION_QUANTITE_SERVIE", origine, injectee


def _quantite_nulle(rng, ligne):
    origine = ligne["PRESTATION_QUANTITE_SERVIE"]
    ligne["PRESTATION_QUANTITE_SERVIE"] = 0
    return "PRESTATION_QUANTITE_SERVIE", origine, 0


def _numero_invalide(rng, ligne):
    origine = ligne["NUMERO_IMMATRICULATION"]
    if rng.random() < 0.5:
        # Trop court : le défaut le plus courant à la saisie.
        injectee = origine[: rng.randint(6, 12)]
    else:
        injectee = origine[:-1] + rng.choice("ABCDEFGH")
    ligne["NUMERO_IMMATRICULATION"] = injectee
    return "NUMERO_IMMATRICULATION", origine, injectee


def _email_invalide(rng, ligne):
    origine = ligne["AGENT_EMAIL"]
    injectee = rng.choice((
        origine.replace("@", ""),
        origine.replace(".ci", ""),
        origine.split("@")[0],
    ))
    ligne["AGENT_EMAIL"] = injectee
    return "AGENT_EMAIL", origine, injectee


def _type_centre_inconnu(rng, ligne):
    origine = ligne["CENTRE_SANTE_TYPE_CODE"]
    injectee = rng.choice(("ZZZ", "XX", "N/A", "INCONNU"))
    ligne["CENTRE_SANTE_TYPE_CODE"] = injectee
    return "CENTRE_SANTE_TYPE_CODE", origine, injectee


def _prestation_orpheline(rng, ligne):
    origine = ligne["PRESTATION_CODE"]
    injectee = f"XXX-{rng.randint(100, 999)}"
    ligne["PRESTATION_CODE"] = injectee
    return "PRESTATION_CODE", origine, injectee


INJECTEURS: dict[str, Injecteur] = {
    MONTANT_ABERRANT: _montant_aberrant,
    MONTANT_HORS_BAREME: _taux_hors_bareme,
    DATE_NAISSANCE_ABERRANTE: _date_naissance_aberrante,
    DATE_ANTIDATEE: _date_antidatee,
    DATE_SOINS_FUTURE: _date_soins_future,
    DATE_HORS_DROITS: _date_hors_droits,
    REPARTITION_FAUSSEE: _repartition_faussee,
    QUANTITE_EXCESSIVE: _quantite_excessive,
    QUANTITE_NULLE: _quantite_nulle,
    NUMERO_SECU_INVALIDE: _numero_invalide,
    EMAIL_INVALIDE: _email_invalide,
    TYPE_CENTRE_INCONNU: _type_centre_inconnu,
    PRESTATION_ORPHELINE: _prestation_orpheline,
}


def ordre_des_types(reglages: dict[str, dict]) -> tuple[str, ...]:
    """Les types actifs, dans l'ordre du catalogue.

    Surtout pas dans l'ordre du dictionnaire de réglages : il vient de l'écran,
    et deux opérateurs qui cochent les mêmes cases dans un ordre différent
    obtiendraient alors deux fichiers différents pour la même graine.
    """

    return tuple(
        code for code in CODES if code in reglages and code in INJECTEURS
    )


def pieger(rng: random.Random, ligne: dict[str, Any], types: tuple[str, ...],
           reglages: dict[str, dict], numero: int) -> list[Constat]:
    """Applique les anomalies tirées pour cette ligne et rend les constats.

    Un tirage est effectué pour **chaque** type actif, même quand un précédent
    a déjà frappé : sauter les suivants ferait dépendre le nombre de tirages
    des résultats précédents, et le taux demandé ne serait plus respecté.
    """

    constats: list[Constat] = []
    for code in types:
        taux = float(reglages[code].get("taux", 0))
        if rng.random() >= taux:
            continue
        champ, origine, injectee = INJECTEURS[code](rng, ligne)
        constats.append(Constat(
            ligne=numero,
            champ=champ,
            anomalie_code=code,
            valeur_origine=_formater(origine),
            valeur_injectee=_formater(injectee),
        ))
    return constats


def _ecrire_entete(fichier: io.TextIOBase) -> None:
    """Pose la ligne d'en-tête, avec les colonnes dans leur ordre déclaré."""

    csv.writer(fichier, delimiter=";", lineterminator="\n").writerow(COLONNES)


def produire(graine: int, volume: int, reglages: dict[str, dict],
             destination: Path,
             progression: Callable[[int], None] | None = None) -> tuple[str, list[Constat], int]:
    """Écrit le jeu piégé et rend son empreinte, son corrigé et son volume.

    L'empreinte est calculée sur les octets réellement écrits : c'est elle qui
    prouve, à l'œil, que deux campagnes de même graine ont produit le même
    fichier.
    """

    rng = random.Random(graine)
    types = ordre_des_types(reglages)
    constats: list[Constat] = []
    empreinte = hashlib.sha256()

    destination.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""` laisse le module csv maîtriser les fins de ligne, et
    # l'encodage est imposé : un fichier écrit en cp1252 sur Windows et en
    # UTF-8 ailleurs n'aurait pas la même empreinte.
    with destination.open("w", newline="", encoding="utf-8") as fichier:
        tampon = io.StringIO()
        ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\n")

        def vider() -> None:
            texte = tampon.getvalue()
            tampon.seek(0)
            tampon.truncate(0)
            fichier.write(texte)
            empreinte.update(texte.encode("utf-8"))

        ecrivain.writerow(COLONNES)
        for numero in range(1, volume + 1):
            ligne = ligne_saine(rng, numero)
            constats.extend(pieger(rng, ligne, types, reglages, numero))
            ecrivain.writerow([_formater(ligne[colonne]) for colonne in COLONNES])

            if numero % PAS_PROGRESSION == 0:
                vider()
                if progression is not None:
                    progression(numero)
        vider()

    if progression is not None:
        progression(volume)
    return empreinte.hexdigest(), constats, volume


def chemin_du_jeu(campagne_id: UUID, reference: str) -> Path:
    """Où le jeu d'une campagne est déposé.

    La référence lisible entre dans le nom : retrouver « C-2026-004 » sur le
    disque ne doit pas demander de traduire un UUID.
    """

    return DOSSIER_JEUX / f"{reference}_{campagne_id}.csv"


def horodatage() -> datetime:
    """L'heure de fin de génération.

    Isolée dans une fonction pour bien marquer qu'elle ne touche **jamais** au
    contenu du jeu : elle date la campagne, pas les données.
    """

    return datetime.now(timezone.utc)
