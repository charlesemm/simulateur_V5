"""Vérifie les types d'anomalies ajoutés et le paramétrage d'un lancement.

Chaque nouveau type doit non seulement s'injecter, mais être retrouvé par une
règle de qualité : un défaut que rien ne détecte n'apprend rien à personne.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from anomalies.catalogue import (
    CATALOGUE_INITIAL, DATE_HORS_DROITS, DATE_SOINS_FUTURE, FAMILLES,
    MONTANT_HORS_BAREME, PRESTATION_ORPHELINE, QUANTITE_NULLE,
    REPARTITION_FAUSSEE, TYPE_CENTRE_INCONNU,
)
from anomalies.config import AnomaliesConfig, Reglage, anomalies_config
from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision
from events import publish_simulation_event
from qualite import analyser
from simulation.passage import PassageSimulation
from simulation.runs import ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT

JOUR = date(2026, 8, 22)


def config(**options) -> AnomaliesConfig:
    """Fabrique une configuration déterministe pour les tests."""

    return AnomaliesConfig(seed=1234, **options)


async def jouer(simulation_id, seed: int = 7) -> None:
    """Exécute un passage complet rattaché à une exécution."""

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, seed, simulation_id,
    ).run()


def regle(rapport, code: str) -> dict:
    return next(ligne for ligne in rapport["regles"] if ligne["code"] == code)


async def jouer_avec(simulation_id, code: str) -> dict:
    """Active un seul type à 100 %, joue un passage, et rend le rapport."""

    anomalies_config.enabled = True
    anomalies_config.reglages[code] = Reglage(taux=1.0)
    try:
        await jouer(simulation_id)
    finally:
        anomalies_config.enabled = False
    return await analyser(simulation_id, inclure_referentiel=False)


# ── Le catalogue couvre les six familles ─────────────────────────────────

def test_les_six_familles_ont_au_moins_un_type():
    familles = {type_anomalie.famille for type_anomalie in CATALOGUE_INITIAL}

    assert familles == set(FAMILLES)


def test_chaque_type_porte_la_couleur_de_sa_famille():
    for type_anomalie in CATALOGUE_INITIAL:
        assert type_anomalie.couleur == FAMILLES[type_anomalie.famille]


# ── Les tirages ──────────────────────────────────────────────────────────

def test_le_taux_hors_bareme_prend_celui_de_l_autre_regime():
    anomalies = config(enabled=True, rate=1.0)

    assert anomalies.tirer_taux(Decimal("70"), "RGB").valeur == Decimal("100")
    assert anomalies.tirer_taux(Decimal("100"), "RAM").valeur == Decimal("70")


def test_la_date_future_depasse_la_marge_de_l_horloge():
    """Sous huit jours, la règle confondrait avec l'aléa d'horloge décalée."""

    anomalies = config(enabled=True, rate=1.0)

    for _ in range(50):
        assert (anomalies.tirer_date_future(JOUR).valeur - JOUR).days >= 8


def test_la_date_hors_droits_change_de_mois():
    anomalies = config(enabled=True, rate=1.0)

    for _ in range(50):
        faussee = anomalies.tirer_date_hors_droits(JOUR).valeur
        assert (JOUR - faussee).days >= 40


def test_la_quantite_nulle_annule_le_servi():
    anomalies = config(enabled=True, rate=1.0)

    assert anomalies.tirer_quantite_nulle(3).valeur == 0


def test_les_codes_orphelins_ne_ressemblent_a_rien_de_connu():
    anomalies = config(enabled=True, rate=1.0)

    assert anomalies.tirer_code_prestation("CONS-GEN").valeur.startswith("INCONNU-")
    assert anomalies.tirer_type_centre("CSU").valeur.startswith("ZZ")


def test_la_date_de_naissance_devient_impossible():
    anomalies = config(enabled=True, rate=1.0)
    naissance = date(1990, 5, 12)

    resultats = [anomalies.tirer_date_naissance(naissance).valeur for _ in range(30)]

    assert all(valeur != naissance for valeur in resultats)
    assert any(valeur > naissance for valeur in resultats)
    assert any(valeur < date(1930, 1, 1) for valeur in resultats)


# ── Bout en bout : injecté puis détecté ──────────────────────────────────

async def test_le_taux_hors_bareme_est_injecte_et_detecte(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, MONTANT_HORS_BAREME)

    async with async_session_factory() as session:
        prestation = (await session.execute(select(InvoiceProvision))).scalars().first()

    # L'assuré de test est au régime RGB, remboursé à 70 %.
    assert prestation.prestation_taux_remboursement == Decimal("100.00")
    assert regle(rapport, "TAUX_HORS_BAREME")["constats"] == 1


async def test_la_repartition_faussee_est_injectee_et_detectee(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, REPARTITION_FAUSSEE)

    assert regle(rapport, "REPARTITION_INCOHERENTE")["constats"] == 1


async def test_la_date_future_est_injectee_et_detectee(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, DATE_SOINS_FUTURE)

    assert regle(rapport, "DATE_SOINS_FUTURE")["constats"] == 1


async def test_la_date_hors_droits_est_injectee_et_detectee(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, DATE_HORS_DROITS)

    # Reculer de plus de quarante jours sort aussi de la marge d'antériorité.
    assert regle(rapport, "DATE_SOINS_ANTIDATEE")["constats"] == 1


async def test_la_quantite_nulle_est_injectee_et_detectee(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, QUANTITE_NULLE)

    assert regle(rapport, "QUANTITE_SERVIE_NULLE")["constats"] == 1


async def test_le_code_de_prestation_orphelin_est_injecte_et_detecte(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, PRESTATION_ORPHELINE)

    assert regle(rapport, "PRESTATION_ORPHELINE")["constats"] == 1


async def test_le_type_de_centre_inconnu_est_injecte_et_detecte(base_vierge):
    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})

    rapport = await jouer_avec(simulation_id, TYPE_CENTRE_INCONNU)

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()

    assert facture.centre_sante_type_code.startswith("ZZ")
    assert regle(rapport, "TYPE_CENTRE_INCONNU")["constats"] == 1


# ── Paramétrage d'un lancement ───────────────────────────────────────────

async def test_le_lancement_accepte_un_nom_et_ses_propres_reglages(client_api):
    """L'écran de lancement doit pouvoir tout décider, sans toucher au catalogue."""

    from anomalies.repository import lire_catalogue

    avant = {
        ligne.anomalie_code: float(ligne.anomalie_taux)
        for ligne in await lire_catalogue()
    }

    demarrage = await client_api.post("/simulation/start", json={
        "type_simulation": "QUALITE",
        "libelle": "Recette qualité du 22 août",
        "vitesse": 3600,
        "nombre_passages_simultanes_max": 1,
        "anomalies": {MONTANT_HORS_BAREME: {"taux": 0.5}},
        "aleas": {"BASE_RALENTIE": {"probabilite": 0.1}},
    })
    assert demarrage.status_code == 202
    simulation_id = demarrage.json()["simulation_id"]
    await client_api.post("/simulation/stop")

    executions = await client_api.get("/simulation/executions")
    execution = next(
        ligne for ligne in executions.json() if ligne["simulation_id"] == simulation_id
    )

    assert execution["simulation_libelle"] == "Recette qualité du 22 août"
    assert execution["simulation_parametres"]["anomalies"][MONTANT_HORS_BAREME]["taux"] == 0.5
    assert execution["simulation_parametres"]["aleas"]["BASE_RALENTIE"]["probabilite"] == 0.1

    # Le catalogue en base n'a pas bougé : les réglages ne valaient que pour
    # cette exécution.
    apres = {
        ligne.anomalie_code: float(ligne.anomalie_taux)
        for ligne in await lire_catalogue()
    }
    assert apres == avant


async def test_sans_nom_le_libelle_reste_l_horodatage(client_api):
    demarrage = await client_api.post("/simulation/start", json={
        "type_simulation": "QUALITE", "vitesse": 3600,
        "nombre_passages_simultanes_max": 1,
    })
    simulation_id = demarrage.json()["simulation_id"]
    await client_api.post("/simulation/stop")

    executions = await client_api.get("/simulation/executions")
    execution = next(
        ligne for ligne in executions.json() if ligne["simulation_id"] == simulation_id
    )

    assert execution["simulation_libelle"].startswith("Exécution du ")
