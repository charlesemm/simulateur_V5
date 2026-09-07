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
import unicodedata
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import UUID

from anomalies.catalogue import (
    CHAMP_OBLIGATOIRE_VIDE, CODES, DATE_ANTIDATEE, DATE_HORS_DROITS,
    DATE_NAISSANCE_ABERRANTE, DATE_SOINS_FUTURE, DOUBLON_APPROCHANT,
    DOUBLON_EXACT, EMAIL_INVALIDE, ENCODAGE_CASSE, FORMAT_DATE_INCOHERENT,
    MONTANT_ABERRANT, MONTANT_HORS_BAREME, NUMERO_SECU_INVALIDE,
    PRESTATION_ORPHELINE, QUANTITE_EXCESSIVE, QUANTITE_NULLE,
    REPARTITION_FAUSSEE, TENTATIVE_INJECTION, TYPE_CENTRE_INCONNU,
)
from seed.constants import (
    HEALTH_CENTER_TYPES, IVORIAN_CITIES, IVORIAN_FIRST_NAMES,
    IVORIAN_LAST_NAMES, MEDICAL_ACTS,
)

logger = logging.getLogger(__name__)


def _agents_accueil() -> tuple[dict[str, str], ...]:
    """Une cinquantaine d'agents d'accueil, à l'image des 50 lignes que le
    seed écrit dans `TB_REF_AGENTS` — même format d'e-mail, même domaine.

    Ce ne sont **pas** les mêmes lignes que la vraie base : le générateur ne
    lit jamais la base (règle du module, pour rester rejouable à graine
    égale), donc cette liste est une référence fixe, écrite ici une fois pour
    toutes plutôt que tirée en base à chaque génération.
    """

    agents = []
    for index in range(50):
        prenom = IVORIAN_FIRST_NAMES[index % len(IVORIAN_FIRST_NAMES)]
        nom = IVORIAN_LAST_NAMES[(index * 7) % len(IVORIAN_LAST_NAMES)]
        racine = f"{prenom}.{nom}".lower().replace("'", "").replace(" ", "")
        agents.append({"prenom": prenom, "nom": nom, "email": f"{racine}.{index + 1}@cmu.demo.ci"})
    return tuple(agents)


# AGENT_EMAIL identifie l'agent d'accueil qui a traité le dossier, pas
# l'assuré qui vient se faire soigner : ce sont deux personnes différentes,
# ce que l'ancienne version de ce générateur confondait.
AGENTS_ACCUEIL = _agents_accueil()

# Où sont déposés les jeux produits. Un dossier à part des rapports : ces
# fichiers ont une autre durée de vie et une autre raison d'être.
DOSSIER_JEUX = Path("campagnes/output")

# Date d'ancrage du jeu produit. **Constante, jamais « aujourd'hui »** : c'est
# ce qui permet à une campagne rejouée dans six mois de produire exactement le
# même fichier qu'aujourd'hui.
DATE_REFERENCE = date(2026, 1, 1)

# Étendue des dates de soins autour de la référence, en jours.
AMPLITUDE_JOURS = 180

# Base du numéro de facture : la première ligne porte 100 000, ce qui donne
# six chiffres pour tous les paliers jusqu'à 900 000 lignes. Au-delà (le
# palier « Afflux soudain » et le plafond de 5 000 000), le nombre grandit
# naturellement à sept chiffres ou plus — jamais tronqué, jamais répété.
FACTURE_NUMERO_BASE = 100_000

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

# ── Le marquage (M4) ────────────────────────────────────────────
#
# Deux colonnes posées d'office en tête de chaque ligne. Aucun réglage ne
# permet de les retirer, et c'est le cahier qui l'exige : un jeu produit par
# ÉCHO ne doit jamais pouvoir être pris pour des données réelles — ni chez
# l'éditeur de l'outil testé, ni dans une base où il aurait été chargé par
# mégarde. Le marquage est en tête, et non en queue, pour qu'il saute aux yeux
# dès la première cellule ouverte.
COLONNE_MARQUE = "DONNEE_FICTIVE"
COLONNE_CAMPAGNE = "CAMPAGNE_REFERENCE"

# La valeur du marquage. Un simple « OUI » se serait perdu dans une colonne
# tronquée ; celle-ci nomme aussi le producteur, ce qui permet de retrouver
# d'où sort un fichier égaré.
MARQUE = "FICTIF-ECHO"

COLONNES_MARQUAGE = (COLONNE_MARQUE, COLONNE_CAMPAGNE)

# Les colonnes réellement écrites dans le fichier, marquage compris.
COLONNES_FICHIER = COLONNES_MARQUAGE + COLONNES

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


IMMATRICULATION_PREFIXE = "394"

# Bijection affine, comme `numero_securite_sociale` dans `seed/runner.py` :
# le multiplicateur est fixé, impair et non multiple de 5, donc premier avec
# le modulo 10**10 — la transformation ne peut alors jamais reboucler sur un
# suffixe déjà attribué. Le décalage, lui, est tiré une fois par génération à
# partir de la graine de la campagne : deux campagnes ne partagent pas la
# même série, mais une campagne rejouée à graine identique produit toujours
# les mêmes numéros.
IMMATRICULATION_MULTIPLICATEUR = 7_919_990_071
IMMATRICULATION_MODULO = 10 ** 10


def _immatriculation(numero: int, decalage: int) -> str:
    """Un numéro d'immatriculation à treize chiffres : préfixe 394 (CMU),
    puis dix chiffres qui paraissent tirés au hasard mais restent uniques
    dans tout le fichier — deux lignes ne peuvent mathématiquement pas
    partager un numéro, ce qui compte pour la dimension Unicité du cahier.
    """

    suffixe = (
        IMMATRICULATION_MULTIPLICATEUR * numero + decalage
    ) % IMMATRICULATION_MODULO
    return f"{IMMATRICULATION_PREFIXE}{suffixe:010d}"


def ligne_saine(
    rng: random.Random, numero: int, decalage_immatriculation: int
) -> dict[str, Any]:
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
        "NUMERO_IMMATRICULATION": _immatriculation(numero, decalage_immatriculation),
        "ASSURE_NOM": nom,
        "ASSURE_PRENOMS": prenom,
        "ASSURE_DATE_NAISSANCE": naissance,
        # L'agent qui a traité le dossier à l'accueil, pas l'assuré qui vient
        # se faire soigner — voir AGENTS_ACCUEIL.
        "AGENT_EMAIL": rng.choice(AGENTS_ACCUEIL)["email"],
        "REGIME_CODE": regime,
        "DROITS_DATE_DEBUT": debut_droits,
        "DROITS_DATE_FIN": fin_droits,
        # Un entier, sans préfixe : six chiffres pour les volumes courants
        # (jusqu'à 900 000 lignes), davantage seulement si le palier l'exige
        # — jamais tronqué, jamais répété entre deux lignes.
        "FACTURE_NUMERO": FACTURE_NUMERO_BASE + numero - 1,
        "FACTURE_DATE_EMISSION": date_emission,
        "FACTURE_DATE_SOINS": date_soins,
        "CENTRE_SANTE_CODE": rng.randint(1, 250),
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

# Un injecteur rend le triplet (champ, valeur d'origine, valeur posée), ou
# None quand il ne peut rien poser sur cette ligne-là — un champ déjà vidé par
# un injecteur précédent, par exemple. Inscrire au corrigé une anomalie qui
# n'a pas eu lieu fausserait le score de M7 dans le mauvais sens : l'outil
# testé serait accusé d'avoir manqué ce qui n'existait pas.
Resultat = tuple[str, Any, Any] | None
Injecteur = Callable[[random.Random, dict[str, Any]], Resultat]
InjecteurContextuel = Callable[
    [random.Random, dict[str, Any], Sequence[dict[str, Any]]], Resultat
]


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


# ── Les injecteurs du chapitre 5 ─────────────────────────────────────────
#
# Le cahier range les caractères cassés et les formats de date parmi les
# « anomalies de fichier », à poser à l'écriture de l'export, au motif
# qu'elles ne peuvent pas exister dans une colonne typée. L'objection tombe
# ici : le jeu est un CSV, où tout est du texte. Les poser dans la ligne comme
# les autres garde le corrigé exact — ligne **et** champ — dont le
# rapprochement de M7 a absolument besoin, et qu'une injection faite à
# l'écriture rendrait bien plus difficile à tenir.

# Les champs qui, ensemble, désignent une personne. Un doublon les copie.
CHAMPS_IDENTITE = (
    "NUMERO_IMMATRICULATION",
    "ASSURE_NOM",
    "ASSURE_PRENOMS",
    "ASSURE_DATE_NAISSANCE",
)

# Ce qu'un dossier ne peut pas laisser vide.
CHAMPS_OBLIGATOIRES = (
    "NUMERO_IMMATRICULATION",
    "ASSURE_NOM",
    "ASSURE_PRENOMS",
    "ASSURE_DATE_NAISSANCE",
    "FACTURE_NUMERO",
    "PRESTATION_CODE",
)

# Champs texte où une charge hostile peut se glisser.
CHAMPS_TEXTE = ("ASSURE_NOM", "ASSURE_PRENOMS", "AGENT_EMAIL", "CENTRE_SANTE_CODE")

# Champs date, pour le format concurrent.
CHAMPS_DATE = ("FACTURE_DATE_SOINS", "ASSURE_DATE_NAISSANCE", "DROITS_DATE_DEBUT")

# Les classiques, ceux qu'on retrouve dans tous les journaux d'accès. Le but
# n'est pas d'attaquer quoi que ce soit : c'est de voir si l'outil testé les
# signale, ou s'il les avale comme un nom de famille ordinaire.
CHARGES_INJECTION = (
    "'; DROP TABLE TB_FACTURES; --",
    "' OR '1'='1",
    "<script>alert(1)</script>",
    "../../../etc/passwd",
    "${jndi:ldap://x}",
    "{{7*7}}",
)

# Formats concurrents de la norme ISO du fichier. Le premier est le piège le
# plus fréquent en Côte d'Ivoire : la date française, que rien ne distingue
# de l'ISO tant que le jour ne dépasse pas douze.
FORMATS_DATE_CONCURRENTS = ("%d/%m/%Y", "%m-%d-%Y", "%Y%m%d", "%d.%m.%y")

# Lignes conservées pour servir de modèle aux doublons. Une fenêtre glissante
# plutôt que tout le fichier : sur un palier à un million de lignes, garder
# chaque identité épuiserait la mémoire pour un bénéfice nul — un doublon posé
# à trois cents lignes d'écart est déjà un doublon.
PROFONDEUR_HISTORIQUE = 300


def _identite(ligne: dict[str, Any]) -> str:
    """L'identité d'une ligne, en une chaîne lisible dans le corrigé."""

    return " | ".join(_formater(ligne[champ]) for champ in CHAMPS_IDENTITE)


def _sans_accents(texte: str) -> str:
    """« Grâce » devient « Grace » — la variation la plus courante."""

    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _varier(rng: random.Random, texte: str) -> str:
    """Une variation orthographique plausible d'un nom.

    Ce sont les vraies causes de doublons flous dans un état civil : un accent
    perdu à la saisie, une consonne doublée, un tiret devenu espace, une casse
    différente selon le guichet.
    """

    # Les deux tirages sont faits d'office, avant tout examen du texte : les
    # rendre conditionnels ferait dépendre la suite du fichier du contenu de
    # la ligne, et l'ordre des tirages ne serait plus le même d'une graine à
    # l'autre.
    forme = rng.randrange(4)
    position = rng.randrange(max(1, len(texte)))
    if not texte:
        return texte

    doublee = texte[:position + 1] + texte[position] + texte[position + 1:]
    match forme:
        case 0:
            variante = _sans_accents(texte)
        case 1:
            variante = texte.upper()
        case 2:
            variante = texte.replace("-", " ").replace("'", " ")
        case _:
            variante = doublee

    # Une variation qui ne varie rien — « Ouattara » sans accent à retirer,
    # un nom déjà en majuscules — donnerait un doublon exact déguisé, et un
    # corrigé annonçant une anomalie que personne ne peut voir. On retombe
    # alors sur le doublement de lettre, qui change toujours quelque chose.
    return variante if variante != texte else doublee


def _doublon_exact(rng, ligne, historique):
    """Recopie à l'identique une personne déjà présente dans le fichier."""

    if not historique:
        return None
    modele = historique[rng.randrange(len(historique))]
    origine = _identite(ligne)
    for champ in CHAMPS_IDENTITE:
        ligne[champ] = modele[champ]
    return "IDENTITE", origine, _identite(ligne)


def _doublon_approchant(rng, ligne, historique):
    """La même personne, à une variation près — et sous un autre numéro.

    L'immatriculation reste celle de la ligne, délibérément : c'est tout le
    cas difficile. Deux numéros pour une seule personne, que seule la
    proximité des noms et la date de naissance permettent de rapprocher. Copier
    aussi le numéro rendrait la détection triviale, et le test sans valeur.
    """

    if not historique:
        return None
    modele = historique[rng.randrange(len(historique))]
    origine = _identite(ligne)
    ligne["ASSURE_NOM"] = _varier(rng, modele["ASSURE_NOM"])
    ligne["ASSURE_PRENOMS"] = modele["ASSURE_PRENOMS"]
    ligne["ASSURE_DATE_NAISSANCE"] = modele["ASSURE_DATE_NAISSANCE"]

    injectee = _identite(ligne)
    # La ligne portait déjà cette identité — un injecteur précédent l'y avait
    # copiée. Rien n'a bougé : ne pas l'inscrire au corrigé, qui annoncerait
    # sinon une anomalie introuvable dans le fichier.
    if injectee == origine:
        return None
    return "IDENTITE", origine, injectee


def _champ_obligatoire_vide(rng, ligne):
    champ = CHAMPS_OBLIGATOIRES[rng.randrange(len(CHAMPS_OBLIGATOIRES))]
    origine = ligne[champ]
    ligne[champ] = ""
    return champ, origine, ""


def _encodage_casse(rng, ligne):
    """Le mojibake du double encodage, ou la lettre devenue « ? ».

    Le tirage de position est fait dans tous les cas, même quand il ne sert
    pas : un tirage conditionnel ferait dépendre la suite du fichier du contenu
    de la ligne, et deux graines identiques ne donneraient plus le même
    résultat.
    """

    champ = CHAMPS_TEXTE[rng.randrange(2)]
    origine = ligne[champ]
    position = rng.randrange(max(1, len(str(origine))))
    if not origine:
        return None

    texte = str(origine)
    # Le double encodage : du texte UTF-8 relu comme du latin-1. C'est
    # exactement ce qu'on voit sur un export mal paramétré.
    casse = texte.encode("utf-8").decode("latin-1")
    if casse == texte:
        # Rien à casser, faute d'accent : on retombe sur le cas que le
        # catalogue cite, la lettre remplacée par un point d'interrogation.
        casse = texte[:position] + "?" + texte[position + 1:]
    ligne[champ] = casse
    return champ, origine, casse


def _format_date_incoherent(rng, ligne):
    """Une date juste, mal écrite."""

    champ = CHAMPS_DATE[rng.randrange(len(CHAMPS_DATE))]
    motif = FORMATS_DATE_CONCURRENTS[rng.randrange(len(FORMATS_DATE_CONCURRENTS))]
    origine = ligne[champ]
    # Un injecteur précédent a pu vider ce champ ou l'avoir déjà réécrit en
    # texte. Ne rien faire alors, plutôt que d'inscrire au corrigé une
    # anomalie qui n'a pas été posée.
    if not isinstance(origine, date):
        return None
    injectee = origine.strftime(motif)
    ligne[champ] = injectee
    return champ, origine, injectee


def _tentative_injection(rng, ligne):
    champ = CHAMPS_TEXTE[rng.randrange(len(CHAMPS_TEXTE))]
    charge = CHARGES_INJECTION[rng.randrange(len(CHARGES_INJECTION))]
    origine = ligne[champ]
    ligne[champ] = charge
    return champ, origine, charge


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
    CHAMP_OBLIGATOIRE_VIDE: _champ_obligatoire_vide,
    ENCODAGE_CASSE: _encodage_casse,
    FORMAT_DATE_INCOHERENT: _format_date_incoherent,
    TENTATIVE_INJECTION: _tentative_injection,
}

# Les deux types qui ne peuvent rien poser sans regarder ce qui précède. Ils
# reçoivent l'historique en plus de la ligne, d'où un dictionnaire à part
# plutôt qu'une troisième position ajoutée aux dix-sept autres signatures.
INJECTEURS_AVEC_HISTORIQUE: dict[str, InjecteurContextuel] = {
    DOUBLON_EXACT: _doublon_exact,
    DOUBLON_APPROCHANT: _doublon_approchant,
}


def ordre_des_types(reglages: dict[str, dict]) -> tuple[str, ...]:
    """Les types actifs, dans l'ordre du catalogue.

    Surtout pas dans l'ordre du dictionnaire de réglages : il vient de l'écran,
    et deux opérateurs qui cochent les mêmes cases dans un ordre différent
    obtiendraient alors deux fichiers différents pour la même graine.
    """

    return tuple(
        code for code in CODES
        if code in reglages
        and (code in INJECTEURS or code in INJECTEURS_AVEC_HISTORIQUE)
    )


def pieger(rng: random.Random, ligne: dict[str, Any], types: tuple[str, ...],
           reglages: dict[str, dict], numero: int,
           historique: Sequence[dict[str, Any]] | None = None) -> list[Constat]:
    """Applique les anomalies tirées pour cette ligne et rend les constats.

    Un tirage est effectué pour **chaque** type actif, même quand un précédent
    a déjà frappé : sauter les suivants ferait dépendre le nombre de tirages
    des résultats précédents, et le taux demandé ne serait plus respecté.
    """

    passe = historique if historique is not None else []
    constats: list[Constat] = []
    for code in types:
        taux = float(reglages[code].get("taux", 0))
        if rng.random() >= taux:
            continue

        if code in INJECTEURS_AVEC_HISTORIQUE:
            resultat = INJECTEURS_AVEC_HISTORIQUE[code](rng, ligne, passe)
        else:
            resultat = INJECTEURS[code](rng, ligne)

        # Rien posé : le tirage a bien eu lieu — la reproductibilité est
        # sauve — mais il n'y a pas d'anomalie à inscrire au corrigé.
        if resultat is None:
            continue

        champ, origine, injectee = resultat
        constats.append(Constat(
            ligne=numero,
            champ=champ,
            anomalie_code=code,
            valeur_origine=_formater(origine),
            valeur_injectee=_formater(injectee),
        ))
    return constats


def produire(graine: int, volume: int, reglages: dict[str, dict],
             destination: Path, reference: str,
             progression: Callable[[int], None] | None = None) -> tuple[str, list[Constat], int]:
    """Écrit le jeu piégé, marqué, et rend son empreinte, son corrigé, son volume.

    **L'empreinte ne couvre que les données, jamais le marquage**, et cette
    exclusion est le seul moyen de tenir les deux exigences du cahier à la
    fois. Le chapitre 3 veut que deux campagnes de même graine affichent la
    même empreinte ; le chapitre 4 veut que chaque ligne porte la référence de
    sa campagne, qui est justement ce qui les distingue. Faire entrer le
    marquage dans le calcul rendrait les deux empreintes différentes et la
    preuve de rejouabilité impossible à lire à l'écran.

    Ce que l'empreinte atteste est donc précis : **le contenu piégé est le
    même**. Elle ne prétend pas être la somme du fichier livré.
    """

    rng = random.Random(graine)
    # Tiré une seule fois, avant la boucle : c'est ce qui distingue la série
    # de numéros d'une campagne de celle d'une autre, sans casser la
    # bijection qui garantit leur unicité au sein du fichier.
    decalage_immatriculation = rng.randrange(IMMATRICULATION_MODULO)
    types = ordre_des_types(reglages)
    constats: list[Constat] = []
    empreinte = hashlib.sha256()

    destination.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""` laisse le module csv maîtriser les fins de ligne, et
    # l'encodage est imposé : un fichier écrit en cp1252 sur Windows et en
    # UTF-8 ailleurs n'aurait pas la même empreinte.
    with destination.open("w", newline="", encoding="utf-8") as fichier:
        # Deux tampons, et non un seul : celui de gauche part sur le disque
        # avec le marquage, celui de droite ne sert qu'au calcul de
        # l'empreinte, sans lui. Recalculer la ligne deux fois coûte moins
        # cher que de découper après coup un texte déjà échappé par le module
        # csv — un point-virgule dans un nom suffirait à fausser la découpe.
        tampon_fichier = io.StringIO()
        ecrivain_fichier = csv.writer(tampon_fichier, delimiter=";", lineterminator="\n")
        tampon_donnees = io.StringIO()
        ecrivain_donnees = csv.writer(tampon_donnees, delimiter=";", lineterminator="\n")

        def vider() -> None:
            fichier.write(tampon_fichier.getvalue())
            tampon_fichier.seek(0)
            tampon_fichier.truncate(0)

            empreinte.update(tampon_donnees.getvalue().encode("utf-8"))
            tampon_donnees.seek(0)
            tampon_donnees.truncate(0)

        ecrivain_fichier.writerow(COLONNES_FICHIER)
        ecrivain_donnees.writerow(COLONNES)

        # Les identités déjà écrites, dans lesquelles les doublons puisent
        # leur modèle. Alimentée **après** le piégeage : sans quoi une ligne
        # pourrait se dupliquer elle-même, ce qui ne prouverait rien.
        historique: deque[dict[str, Any]] = deque(maxlen=PROFONDEUR_HISTORIQUE)

        for numero in range(1, volume + 1):
            ligne = ligne_saine(rng, numero, decalage_immatriculation)
            constats.extend(
                pieger(rng, ligne, types, reglages, numero, historique)
            )
            historique.append({champ: ligne[champ] for champ in CHAMPS_IDENTITE})
            cellules = [_formater(ligne[colonne]) for colonne in COLONNES]
            ecrivain_fichier.writerow([MARQUE, reference, *cellules])
            ecrivain_donnees.writerow(cellules)

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
