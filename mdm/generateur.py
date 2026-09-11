"""T2 — Fabrique des identités volontairement jumelles, et dit lesquelles.

Le rapprochement d'identités ne s'évalue pas sur des données réelles : on y
ignore combien de doublons ont échappé. Ici, chaque variante est produite à
partir d'une identité connue, et la paire est consignée avec sa réponse.

Des leurres complètent le jeu : deux personnes qui se ressemblent sans être la
même. Sans eux, un moteur qui rapproche tout obtiendrait un rappel parfait.
"""

from __future__ import annotations

import logging
import random
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import InsuredPerson
from mdm.models import MdmPair
from seed.identifiants import numero_libre, numero_securite_sociale_libre

logger = logging.getLogger(__name__)

# Types de variation produits. Ils nomment ce qui a été modifié, ce qui permet
# ensuite de dire quelle sorte de variation échappe au rapprochement.
ORTHOGRAPHE = "ORTHOGRAPHE"
ACCENTS = "ACCENTS"
PRENOM_ABREGE = "PRENOM_ABREGE"
NOM_INVERSE = "NOM_INVERSE"
DATE_DECALEE = "DATE_DECALEE"
NUMERO_PROCHE = "NUMERO_PROCHE"
HOMONYME = "HOMONYME"

VARIATIONS = (
    ORTHOGRAPHE, ACCENTS, PRENOM_ABREGE, NOM_INVERSE, DATE_DECALEE, NUMERO_PROCHE,
)

# Substitutions courantes dans les patronymes ivoiriens saisis à l'oreille.
SUBSTITUTIONS = (("I", "Y"), ("OU", "U"), ("SS", "S"), ("É", "E"), ("PH", "F"))


@dataclass
class Variante:
    """Ce qu'une variation a produit, avant écriture."""

    personne: InsuredPerson
    type_variation: str
    meme_personne: bool
    commentaire: str


def _sans_accents(valeur: str) -> str:
    """Retire les accents, comme le ferait une saisie sur clavier limité."""

    decompose = unicodedata.normalize("NFD", valeur)
    return "".join(lettre for lettre in decompose if unicodedata.category(lettre) != "Mn")


def _orthographe_proche(valeur: str, tirage: random.Random) -> str:
    """Applique une substitution phonétique, ou double une lettre."""

    for origine, remplacement in tirage.sample(SUBSTITUTIONS, len(SUBSTITUTIONS)):
        if origine in valeur.upper():
            return valeur.upper().replace(origine, remplacement, 1)
    position = tirage.randrange(len(valeur))
    return valeur[:position] + valeur[position] + valeur[position:]


def _numero_proche(numero: str, tirage: random.Random) -> str:
    """Change un seul chiffre : la faute de frappe la plus banale."""

    if not numero:
        return numero
    position = tirage.randrange(len(numero))
    chiffre = numero[position]
    if not chiffre.isdigit():
        return numero
    remplacant = str((int(chiffre) + tirage.choice([1, 2, 8, 9])) % 10)
    return numero[:position] + remplacant + numero[position + 1:]


def _numero_libre(base: str, tirage: random.Random, pris: set[str]) -> str:
    """Trouve un numéro proche encore libre : la colonne est unique en base."""

    for _ in range(50):
        candidat = _numero_proche(base, tirage)
        if candidat != base and candidat not in pris:
            pris.add(candidat)
            return candidat
    # Dernier recours : un numéro clairement distinct, au format réel (394 +
    # dix chiffres), tiré hors des rangs semés.
    candidat = numero_securite_sociale_libre(tirage)
    pris.add(candidat)
    return candidat


def _fabriquer(source: InsuredPerson, variation: str, tirage: random.Random,
               numeros_pris: set[str]) -> Variante:
    """Construit une variante d'une identité, selon le type demandé."""

    personne = InsuredPerson(
        personne_uuid=uuid.uuid4(),
        numero_secu=_numero_libre(source.numero_secu, tirage, numeros_pris),
        # Une nouvelle fiche reçoit ses propres numéros, au format réel : c'est
        # l'identité, pas le numéro, qui doit trahir la jumelle.
        numero_recepisse=numero_libre("recepisse", tirage),
        assure_numero_identifiant=numero_libre("assure_identifiant", tirage),
        civilite_code=source.civilite_code,
        assure_nom=source.assure_nom,
        assure_prenoms=source.assure_prenoms,
        assure_date_naissance=source.assure_date_naissance,
        regime_code=source.regime_code,
        utilisateur_id_creation="mdm",
    )

    if variation == ORTHOGRAPHE:
        personne.assure_nom = _orthographe_proche(source.assure_nom, tirage)
        commentaire = f"{source.assure_nom} écrit {personne.assure_nom}"
    elif variation == ACCENTS:
        personne.assure_nom = _sans_accents(source.assure_nom)
        personne.assure_prenoms = _sans_accents(source.assure_prenoms or "")
        commentaire = "Saisie sans accents"
    elif variation == PRENOM_ABREGE:
        prenoms = (source.assure_prenoms or "").split()
        personne.assure_prenoms = (
            f"{prenoms[0][0]}." if prenoms else "X."
        )
        commentaire = "Prénom réduit à son initiale"
    elif variation == NOM_INVERSE:
        personne.assure_nom = (source.assure_prenoms or source.assure_nom).split()[0]
        personne.assure_prenoms = source.assure_nom
        commentaire = "Nom et prénoms intervertis"
    elif variation == DATE_DECALEE:
        if source.assure_date_naissance:
            personne.assure_date_naissance = source.assure_date_naissance + timedelta(
                days=tirage.choice([-1, 1])
            )
        commentaire = "Date de naissance décalée d'un jour"
    else:  # NUMERO_PROCHE : seul le numéro change.
        commentaire = "Numéro de sécurité sociale à un chiffre près"

    return Variante(personne, variation, True, commentaire)


def _fabriquer_leurre(source: InsuredPerson, tirage: random.Random,
                      numeros_pris: set[str]) -> Variante:
    """Fabrique un homonyme : même identité civile, autre personne.

    Une date de naissance franchement différente en fait quelqu'un d'autre —
    et c'est au moteur de rapprochement de ne pas s'y tromper.
    """

    personne = InsuredPerson(
        personne_uuid=uuid.uuid4(),
        numero_secu=_numero_libre(source.numero_secu, tirage, numeros_pris),
        numero_recepisse=numero_libre("recepisse", tirage),
        assure_numero_identifiant=numero_libre("assure_identifiant", tirage),
        civilite_code=source.civilite_code,
        assure_nom=source.assure_nom,
        assure_prenoms=source.assure_prenoms,
        assure_date_naissance=(
            source.assure_date_naissance - timedelta(days=tirage.randrange(3000, 9000))
            if source.assure_date_naissance else None
        ),
        regime_code=source.regime_code,
        utilisateur_id_creation="mdm",
    )
    return Variante(personne, HOMONYME, False, "Homonyme né bien plus tôt")


async def generer_variantes(simulation_id: uuid.UUID | None = None,
                            nombre: int = 20, part_leurres: float = 0.25,
                            graine: int = 42) -> dict[str, int]:
    """Crée des identités jumelles et consigne la vérité terrain.

    Retourne le compte de ce qui a été produit. Le tirage est ensemencé : à
    graine égale, le même jeu se reconstruit.
    """

    tirage = random.Random(graine)

    async with async_session_factory() as session:
        sources = list((await session.execute(
            select(InsuredPerson).order_by(func.random()).limit(nombre)
        )).scalars())
        if not sources:
            raise RuntimeError("Aucun assuré en base : lancez le seed d'abord.")

        numeros_pris = set((await session.execute(
            select(InsuredPerson.numero_secu)
        )).scalars())

        variantes: list[Variante] = []
        for source in sources:
            if tirage.random() < part_leurres:
                variantes.append(_fabriquer_leurre(source, tirage, numeros_pris))
            else:
                variantes.append(
                    _fabriquer(source, tirage.choice(VARIATIONS), tirage, numeros_pris)
                )

        for source, variante in zip(sources, variantes):
            session.add(variante.personne)
            session.add(MdmPair(
                paire_id=uuid.uuid4(),
                simulation_id=simulation_id,
                personne_uuid_source=source.personne_uuid,
                personne_uuid_variante=variante.personne.personne_uuid,
                type_variation=variante.type_variation,
                meme_personne=variante.meme_personne,
                commentaire=variante.commentaire,
                utilisateur_id_creation="mdm",
            ))
        await session.commit()

    doublons = sum(1 for variante in variantes if variante.meme_personne)
    logger.info("MDM : %s variantes dont %s leurres.", len(variantes), len(variantes) - doublons)
    return {
        "paires": len(variantes),
        "doublons_reels": doublons,
        "leurres": len(variantes) - doublons,
    }
