"""Inscrit un nouvel assuré en cours d'exécution, pour porter une anomalie d'identité.

Le moteur temps réel ne crée jamais d'assuré : `SimulationEngine._reserve_insured`
pioche toujours parmi ceux du référentiel semé à l'avance. Cinq types du
catalogue visent pourtant l'identité de l'assuré lui-même — un doublon, un
champ obligatoire vide, un nom cassé à l'encodage, une tentative d'injection —
et n'avaient donc jamais de ligne à corrompre : la campagne seule savait les
poser, sur le fichier qu'elle compose elle-même ligne par ligne.

Ce module comble l'écart, sans toucher au reste du moteur : il enregistre une
fiche neuve dans TB_REF_ASSURES, la corrompt selon le type demandé, lui ouvre
des droits pour le mois en cours, et rend son identifiant pour qu'un passage
ordinaire s'en empare ensuite — exactement comme s'il avait été semé.
"""

from __future__ import annotations

import random
import unicodedata
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select

from anomalies.catalogue import (
    CHAMP_OBLIGATOIRE_VIDE, DOUBLON_APPROCHANT, DOUBLON_EXACT,
    ENCODAGE_CASSE, TENTATIVE_INJECTION,
)
from anomalies.config import AnomaliesConfig, Injection
from anomalies.repository import enregistrer_injections
from app.database import async_session_factory
from app.models import InsuredPerson, InsuredRight, Regime
from seed.constants import IVORIAN_FIRST_NAMES, IVORIAN_LAST_NAMES
from seed.identifiants import numero_libre, numero_securite_sociale_libre

# Les cinq types d'identité, dans l'ordre du catalogue : un seul agit par
# assuré inscrit, le premier dont le tirage du taux réussit.
CODES_IDENTITE = (
    DOUBLON_EXACT, DOUBLON_APPROCHANT, CHAMP_OBLIGATOIRE_VIDE,
    ENCODAGE_CASSE, TENTATIVE_INJECTION,
)

# Les classiques des journaux d'accès, les mêmes que la campagne pose dans un
# fichier : le but n'est pas d'attaquer quoi que ce soit, seulement de voir si
# l'outil testé les signale ou les avale comme un nom de famille ordinaire.
CHARGES_INJECTION = (
    "'; DROP TABLE TB_FACTURES; --",
    "' OR '1'='1",
    "<script>alert(1)</script>",
    "../../../etc/passwd",
    "${jndi:ldap://x}",
    "{{7*7}}",
)


def _sans_accents(texte: str) -> str:
    """« Grâce » devient « Grace » — la variation la plus courante d'un nom."""

    decompose = unicodedata.normalize("NFD", texte)
    return "".join(caractere for caractere in decompose
                   if unicodedata.category(caractere) != "Mn")


def _varier(rng: random.Random, texte: str) -> str:
    """Une variation orthographique plausible, pour le doublon approchant.

    Même geste que `campagnes.generateur._varier` : un accent perdu, une
    consonne doublée, un tiret devenu espace, une casse différente. Dupliqué
    plutôt qu'importé — la campagne reste un module à part, déterministe et
    sans base, que ce module n'a aucune raison de coupler au sien.
    """

    if not texte:
        return texte
    forme = rng.randrange(4)
    position = rng.randrange(len(texte))
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
    return variante if variante != texte else doublee


def _casser_encodage(texte: str) -> str:
    """Le mojibake du double encodage, ou la lettre devenue « ? »."""

    if not texte:
        return "?"
    casse = texte.encode("utf-8").decode("latin-1")
    if casse == texte:
        casse = texte[:1] + "?" + texte[1:]
    return casse


def code_identite_a_inscrire(config: AnomaliesConfig) -> str | None:
    """Dit quel type d'identité inscrire ce tour, ou rien s'il n'y a rien à poser.

    Mêmes taux, mêmes moments que tout autre type du catalogue : c'est
    `should_inject` qui décide, réglages de la console compris.
    """

    for code in CODES_IDENTITE:
        if config.should_inject(code):
            return code
    return None


async def inscrire_assure(code: str, rng: random.Random,
                          simulation_id: UUID | None,
                          config: AnomaliesConfig) -> UUID:
    """Crée une fiche assuré neuve porteuse de l'anomalie `code`, droits ouverts."""

    personne_uuid = uuid4()
    aujourdhui = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        if code in (DOUBLON_EXACT, DOUBLON_APPROCHANT):
            # Le doublon copie une personne déjà présente dans le
            # référentiel : c'est le cas réel, une fiche recréée pour un
            # assuré qui en avait déjà une.
            modele = (await session.execute(
                select(InsuredPerson).order_by(func.random()).limit(1)
            )).scalar_one()
            origine = f"{modele.assure_nom} {modele.assure_prenoms or ''}".strip()
            nom = modele.assure_nom if code == DOUBLON_EXACT else _varier(rng, modele.assure_nom)
            prenoms = modele.assure_prenoms
            naissance = modele.assure_date_naissance
        else:
            nom = IVORIAN_LAST_NAMES[rng.randrange(len(IVORIAN_LAST_NAMES))]
            prenoms = IVORIAN_FIRST_NAMES[rng.randrange(len(IVORIAN_FIRST_NAMES))]
            naissance = date(1940 + rng.randrange(70), rng.randint(1, 12), rng.randint(1, 28))
            origine = nom

            if code == CHAMP_OBLIGATOIRE_VIDE:
                nom = ""
            elif code == ENCODAGE_CASSE:
                nom = _casser_encodage(nom)
            elif code == TENTATIVE_INJECTION:
                nom = CHARGES_INJECTION[rng.randrange(len(CHARGES_INJECTION))]

        regime_code = (await session.execute(
            select(Regime.regime_code).order_by(func.random()).limit(1)
        )).scalar_one()

        session.add(InsuredPerson(
            personne_uuid=personne_uuid,
            # Même format que le seed (394 + dix chiffres), tiré hors des rangs
            # semés : aucune collision possible avec un numéro existant.
            numero_secu=numero_securite_sociale_libre(rng),
            assure_nom=nom,
            assure_prenoms=prenoms,
            assure_date_naissance=naissance,
            regime_code=regime_code,
            utilisateur_id_creation="simulation",
        ))
        session.add(InsuredRight(
            personne_uuid=personne_uuid,
            droits_annee=aujourdhui.year,
            droits_mois=aujourdhui.month,
            droits_id=numero_libre("droits", rng),
            droits_statut=1,
            droits_date_debut=aujourdhui,
            utilisateur_id_creation="simulation",
        ))
        await session.commit()

    config.record_injection()
    await enregistrer_injections([Injection(
        anomalie_code=code,
        valeur_origine=origine,
        valeur_injectee=nom,
        cible_cle=str(personne_uuid),
        passage_id=None,
        simulation_id=simulation_id,
    )])

    return personne_uuid
