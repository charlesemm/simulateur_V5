"""L'inscription d'un assuré neuf, seule porte d'entrée des cinq anomalies

qui visaient jusqu'ici une table que le moteur temps réel n'écrivait jamais.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from anomalies.catalogue import (
    CHAMP_OBLIGATOIRE_VIDE, DOUBLON_APPROCHANT, DOUBLON_EXACT, ENCODAGE_CASSE,
    TENTATIVE_INJECTION,
)
from anomalies.config import anomalies_config
from anomalies.models import AnomalyInjection
from app.database import async_session_factory
from app.models import InsuredPerson, InsuredRight
from simulation.inscription import (
    CHARGES_INJECTION, code_identite_a_inscrire, inscrire_assure,
)

pytestmark = pytest.mark.usefixtures("base_vierge")


async def _inscrire(code: str, graine: int = 1) -> InsuredPerson:
    personne_uuid = await inscrire_assure(code, random.Random(graine), None, anomalies_config)
    async with async_session_factory() as session:
        return await session.get(InsuredPerson, personne_uuid)


async def _noms_deja_semes(exclure: object) -> set[str]:
    async with async_session_factory() as session:
        return set((await session.execute(
            select(InsuredPerson.assure_nom)
            .where(InsuredPerson.personne_uuid != exclure)
        )).scalars())


async def test_code_identite_a_inscrire_ne_propose_rien_a_taux_nul():
    """Le catalogue arrive à taux nul (base_vierge) : rien ne se déclenche seul."""

    anomalies_config.enabled = True
    assert code_identite_a_inscrire(anomalies_config) is None


async def test_champ_obligatoire_vide_ecrit_un_nom_vide():
    fiche = await _inscrire(CHAMP_OBLIGATOIRE_VIDE)
    assert fiche is not None
    assert fiche.assure_nom == ""


async def test_encodage_casse_produit_un_nom_non_vide():
    fiche = await _inscrire(ENCODAGE_CASSE)
    assert fiche.assure_nom != ""


async def test_tentative_injection_ecrit_une_charge_connue():
    fiche = await _inscrire(TENTATIVE_INJECTION)
    assert fiche.assure_nom in CHARGES_INJECTION


async def test_doublon_exact_copie_une_identite_deja_presente():
    fiche = await _inscrire(DOUBLON_EXACT)
    assert fiche.assure_nom in await _noms_deja_semes(fiche.personne_uuid)


async def test_doublon_approchant_varie_le_nom():
    fiche = await _inscrire(DOUBLON_APPROCHANT)
    assert fiche.assure_nom not in await _noms_deja_semes(fiche.personne_uuid)


async def test_l_assure_inscrit_a_des_droits_ouverts_ce_mois():
    fiche_uuid = await inscrire_assure(
        CHAMP_OBLIGATOIRE_VIDE, random.Random(2), None, anomalies_config
    )
    aujourdhui = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        droits = await session.get(
            InsuredRight, (fiche_uuid, aujourdhui.year, aujourdhui.month)
        )
    assert droits is not None
    assert droits.droits_statut == 1


async def test_l_inscription_est_journalisee():
    fiche_uuid = await inscrire_assure(
        TENTATIVE_INJECTION, random.Random(3), None, anomalies_config
    )
    async with async_session_factory() as session:
        journal = (await session.execute(
            select(AnomalyInjection).where(AnomalyInjection.cible_cle == str(fiche_uuid))
        )).scalar_one()
    assert journal.anomalie_code == TENTATIVE_INJECTION
