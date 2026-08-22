"""Vérifie que le moteur de qualité détecte ce que le simulateur a cassé.

La confrontation au journal d'injection est le cœur du chantier : sans elle,
un rapport de qualité ne dit jamais ce qui lui a échappé.
"""
from __future__ import annotations

import pytest

from anomalies.catalogue import MONTANT_ABERRANT, QUANTITE_EXCESSIVE
from anomalies.config import Reglage, anomalies_config
from events import publish_simulation_event
from qualite import analyser
from qualite.regles import COHERENCE, COMPLETUDE, UNICITE, VALIDITE
from simulation.aleas import COUPURE_BRUTALE, PassageInterrompu, ScenarioAleas
from simulation.passage import PassageSimulation
from simulation.runs import ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT


async def jouer(simulation_id, scenario: ScenarioAleas | None = None, seed: int = 7):
    """Exécute un passage complet rattaché à une exécution."""

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, seed, simulation_id, scenario,
    ).run()


def regle(rapport, code: str) -> dict:
    """Retrouve une règle dans le rapport."""

    return next(ligne for ligne in rapport["regles"] if ligne["code"] == code)


def confrontation(rapport, code: str) -> dict:
    """Retrouve une ligne de confrontation dans le rapport."""

    return next(
        ligne for ligne in rapport["confrontation"] if ligne["anomalie_code"] == code
    )


async def test_un_passage_sain_ne_produit_aucun_constat(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)

    rapport = await analyser(simulation_id, inclure_referentiel=False)

    assert rapport["total_constats"] == 0
    assert all(valeur == 0 for valeur in rapport["par_dimension"].values())


async def test_les_montants_aberrants_sont_detectes_et_confrontes(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    anomalies_config.enabled = True
    anomalies_config.reglages[MONTANT_ABERRANT] = Reglage(taux=1.0)
    try:
        await jouer(simulation_id)
    finally:
        anomalies_config.enabled = False

    rapport = await analyser(simulation_id, inclure_referentiel=False)
    ligne = confrontation(rapport, MONTANT_ABERRANT)

    assert ligne["injectees"] >= 1
    assert ligne["detectees"] >= 1
    assert rapport["par_dimension"][VALIDITE] >= 1
    # Le rapport doit montrer la ligne fautive, pas seulement la compter.
    negatifs = regle(rapport, "MONTANT_NEGATIF")
    demesures = regle(rapport, "MONTANT_DEMESURE")
    assert negatifs["constats"] + demesures["constats"] >= 1
    assert (negatifs["exemples"] or demesures["exemples"])


async def test_les_quantites_excessives_sont_detectees(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    anomalies_config.enabled = True
    anomalies_config.reglages[QUANTITE_EXCESSIVE] = Reglage(taux=1.0)
    try:
        await jouer(simulation_id)
    finally:
        anomalies_config.enabled = False

    rapport = await analyser(simulation_id, inclure_referentiel=False)

    assert regle(rapport, "QUANTITE_SERVIE_EXCESSIVE")["constats"] >= 1
    assert rapport["par_dimension"][COHERENCE] >= 1
    assert confrontation(rapport, QUANTITE_EXCESSIVE)["taux_detection_pourcent"] is not None


async def test_une_coupure_laisse_une_facture_sans_cloture(base_vierge):
    """La règle de cohérence doit voir ce que l'aléa a laissé derrière lui."""

    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})
    scenario = ScenarioAleas()
    scenario.reglages[COUPURE_BRUTALE]["probabilite"] = 1.0

    with pytest.raises(PassageInterrompu):
        await jouer(simulation_id, scenario)

    rapport = await analyser(simulation_id, inclure_referentiel=False)

    assert regle(rapport, "FACTURE_SANS_CLOTURE")["constats"] == 1
    assert regle(rapport, "FACTURE_SANS_PRESTATION")["constats"] == 1
    assert rapport["par_dimension"][COMPLETUDE] >= 1


async def test_les_regles_referentielles_ignorent_l_execution(base_vierge):
    """Le seed corrompt le référentiel avant qu'aucune exécution n'existe."""

    del base_vierge
    from app.database import async_session_factory
    from app.models import Agent

    async with async_session_factory() as session:
        agent = await session.get(Agent, "AG0001")
        agent.agent_email = "pas_un_email_valide"
        await session.commit()

    simulation_id = await ouvrir_execution({"vitesse": 60})
    rapport = await analyser(simulation_id, inclure_referentiel=True)

    assert regle(rapport, "EMAIL_AGENT_INVALIDE")["constats"] == 1

    # Sans le référentiel, la même analyse ne relève plus rien.
    sans_referentiel = await analyser(simulation_id, inclure_referentiel=False)
    assert all(
        ligne["code"] != "EMAIL_AGENT_INVALIDE" for ligne in sans_referentiel["regles"]
    )


async def test_une_identite_en_double_est_relevee(base_vierge):
    """Le numéro de sécurité sociale est protégé par contrainte, pas l'identité."""

    del base_vierge
    from app.database import async_session_factory
    from app.models import InsuredPerson
    from tests.conftest import ASSURE_SANS_DROITS

    async with async_session_factory() as session:
        premier = await session.get(InsuredPerson, ASSURE_COUVERT)
        second = await session.get(InsuredPerson, ASSURE_SANS_DROITS)
        second.assure_nom = premier.assure_nom
        second.assure_prenoms = premier.assure_prenoms
        second.assure_date_naissance = premier.assure_date_naissance
        await session.commit()

    rapport = await analyser(None, inclure_referentiel=True)

    assert regle(rapport, "IDENTITE_EN_DOUBLE")["constats"] == 1
    assert rapport["par_dimension"][UNICITE] == 1


async def test_le_rapport_d_une_execution_inconnue_est_refuse(base_vierge):
    del base_vierge
    import uuid

    with pytest.raises(LookupError):
        await analyser(uuid.uuid4())


async def test_l_api_expose_le_rapport(client_api):
    simulation_id = await ouvrir_execution({"vitesse": 60})
    await jouer(simulation_id)

    reponse = await client_api.get(
        f"/qualite/rapport?simulation_id={simulation_id}&inclure_referentiel=false"
    )

    assert reponse.status_code == 200
    rapport = reponse.json()
    assert rapport["simulation_id"] == str(simulation_id)
    assert "confrontation" in rapport

    regles = await client_api.get("/qualite/regles")
    assert regles.status_code == 200
    assert len(regles.json()) >= 10
