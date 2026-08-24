"""Vérifie le moment d'injection, les scénarios d'aléa et les quatre profils.

Trois chantiers du socle qui ne se voient pas à l'écran : quand une anomalie
entre en scène, ce qui arrive quand le moteur est maltraité, et ce que change
le choix d'un type de simulation.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from anomalies.catalogue import (
    DECLENCHEMENT_DEMARRAGE, DECLENCHEMENT_DIFFERE, DECLENCHEMENT_MANUEL,
    MONTANT_ABERRANT,
)
from anomalies.config import AnomaliesConfig, Reglage
from app.database import async_session_factory
from app.models import Invoice, InvoiceStatus
from events import publish_simulation_event
from simulation.aleas import (
    BASE_RALENTIE, COUPURE_BRUTALE, HORLOGE_DECALEE, RAFALE,
    PassageInterrompu, ScenarioAleas,
)
from simulation.commandes import (
    ARMER_ANOMALIE, DECLENCHER_ALEA, CanalDeCommande, Commande,
)
from simulation.passage import PassageSimulation
from simulation.profils import ENTREPOT, GOUVERNANCE, LIBRE, MDM, PROFILS, QUALITE, profil
from simulation.runs import ouvrir_execution
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT

REFERENCE = Decimal("10000")


def config(**options) -> AnomaliesConfig:
    """Fabrique une configuration déterministe pour les tests."""

    return AnomaliesConfig(seed=1234, **options)


# ── S3 : le moment d'injection ────────────────────────────────────────────

def test_le_type_differe_se_tait_avant_son_delai():
    anomalies = config(enabled=True, rate=1.0)
    anomalies.reglages[MONTANT_ABERRANT] = Reglage(
        declenchement=DECLENCHEMENT_DIFFERE, delai_secondes=60
    )

    anomalies.debut_execution = datetime.now(timezone.utc)
    assert anomalies.injecter_montant(REFERENCE) == REFERENCE

    # Le moteur tourne depuis deux minutes : le type entre en scène.
    anomalies.debut_execution = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert anomalies.injecter_montant(REFERENCE) != REFERENCE


def test_le_type_de_demarrage_se_tait_apres_sa_fenetre():
    anomalies = config(enabled=True, rate=1.0)
    anomalies.reglages[MONTANT_ABERRANT] = Reglage(
        declenchement=DECLENCHEMENT_DEMARRAGE, delai_secondes=60
    )

    anomalies.debut_execution = datetime.now(timezone.utc)
    assert anomalies.injecter_montant(REFERENCE) != REFERENCE

    anomalies.debut_execution = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert anomalies.injecter_montant(REFERENCE) == REFERENCE


def test_le_type_manuel_attend_d_etre_arme():
    anomalies = config(enabled=True, rate=1.0)
    anomalies.reglages[MONTANT_ABERRANT] = Reglage(declenchement=DECLENCHEMENT_MANUEL)

    assert anomalies.injecter_montant(REFERENCE) == REFERENCE

    anomalies.armer(MONTANT_ABERRANT)
    assert anomalies.injecter_montant(REFERENCE) != REFERENCE

    anomalies.armer(MONTANT_ABERRANT, False)
    assert anomalies.injecter_montant(REFERENCE) == REFERENCE


def test_demarrer_une_execution_desarme_les_types_manuels():
    """Un armement ne doit pas survivre à l'exécution qui l'a reçu."""

    anomalies = config(enabled=True, rate=1.0)
    anomalies.reglages[MONTANT_ABERRANT] = Reglage(declenchement=DECLENCHEMENT_MANUEL)
    anomalies.armer(MONTANT_ABERRANT)

    anomalies.demarrer_execution()

    assert anomalies.reglages[MONTANT_ABERRANT].arme is False
    assert anomalies.injecter_montant(REFERENCE) == REFERENCE


def test_le_canal_transporte_les_ordres_dans_l_ordre():
    canal = CanalDeCommande()
    assert canal.deposer(Commande(ARMER_ANOMALIE, MONTANT_ABERRANT))
    assert canal.deposer(Commande(DECLENCHER_ALEA, COUPURE_BRUTALE))
    assert canal.en_attente() == 2

    ordres = canal.vider()
    assert [commande.cible for commande in ordres] == [MONTANT_ABERRANT, COUPURE_BRUTALE]
    assert canal.vider() == []


def test_le_canal_sature_refuse_sans_lever():
    canal = CanalDeCommande(taille_maximale=1)
    assert canal.deposer(Commande(ARMER_ANOMALIE, MONTANT_ABERRANT))
    assert canal.deposer(Commande(ARMER_ANOMALIE, MONTANT_ABERRANT)) is False


# ── S4 : les scénarios d'aléa ─────────────────────────────────────────────

def test_un_alea_a_l_arret_ne_tire_rien():
    """Sans cette garde, activer les aléas casserait la reproductibilité."""

    scenario = ScenarioAleas()
    tirage = random.Random(7)
    temoin = random.Random(7)

    assert scenario.frappe(COUPURE_BRUTALE, tirage) is False
    # La suite aléatoire n'a pas bougé.
    assert tirage.random() == temoin.random()


def test_un_alea_arme_frappe_une_seule_fois():
    scenario = ScenarioAleas()
    scenario.armer(COUPURE_BRUTALE)
    tirage = random.Random(7)

    assert scenario.frappe(COUPURE_BRUTALE, tirage) is True
    assert scenario.frappe(COUPURE_BRUTALE, tirage) is False


def test_un_alea_certain_frappe_toujours():
    scenario = ScenarioAleas()
    scenario.reglages[COUPURE_BRUTALE]["probabilite"] = 1.0
    tirage = random.Random(7)

    assert all(scenario.frappe(COUPURE_BRUTALE, tirage) for _ in range(20))


def test_chaque_alea_declare_les_reglages_qu_il_accepte():
    """Un écran ne peut proposer que ce que le moteur déclare accepter."""

    from simulation.aleas import ALEAS, DEFAUTS, PARAMETRES

    assert set(PARAMETRES) == set(ALEAS)
    for code, reglages in PARAMETRES.items():
        for reglage in reglages:
            # Le nom doit correspondre à une clé réellement lue par le moteur.
            assert reglage.nom in DEFAUTS[code], (code, reglage.nom)
            assert reglage.defaut == DEFAUTS[code][reglage.nom]
            assert reglage.minimum <= reglage.defaut <= reglage.maximum
            assert reglage.libelle and reglage.unite


def test_les_aleas_sans_reglage_n_en_declarent_aucun():
    """Une coupure frappe ou ne frappe pas : rien à régler."""

    from simulation.aleas import PARAMETRES, PERTE_CONNEXION

    assert PARAMETRES[COUPURE_BRUTALE] == ()
    assert PARAMETRES[PERTE_CONNEXION] == ()


def test_un_reglage_transmis_est_bien_applique():
    """Ce que l'écran envoie doit atteindre le moteur, pas rester en route."""

    scenario = ScenarioAleas.depuis_parametres(
        {RAFALE: {"probabilite": 0.5, "taille": 120}}
    )

    assert scenario.reglage(RAFALE, "taille", 25) == 120
    assert scenario.en_parametres()[RAFALE]["taille"] == 120


def test_seuls_les_aleas_actifs_sont_retenus_sur_l_execution():
    scenario = ScenarioAleas()
    scenario.reglages[BASE_RALENTIE]["probabilite"] = 0.3

    parametres = scenario.en_parametres()

    assert set(parametres) == {BASE_RALENTIE}
    assert parametres[BASE_RALENTIE]["probabilite"] == 0.3


async def test_la_coupure_laisse_la_facture_ouverte(base_vierge):
    """C'est l'incohérence recherchée : une facture sans clôture."""

    del base_vierge
    simulation_id = await ouvrir_execution({"vitesse": 60})
    scenario = ScenarioAleas()
    scenario.reglages[COUPURE_BRUTALE]["probabilite"] = 1.0

    passage = PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, simulation_id, scenario,
    )

    try:
        await passage.run()
    except PassageInterrompu as coupure:
        assert coupure.alea in (COUPURE_BRUTALE,)
    else:
        raise AssertionError("Le passage aurait dû être coupé.")

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()
        statuts = [ligne.statut_code for ligne in (
            await session.execute(select(InvoiceStatus))
        ).scalars()]

    assert facture is not None
    assert "ouverte" in statuts
    assert "cloturee" not in statuts


async def test_l_horloge_decalee_deplace_la_date_de_soins(base_vierge):
    del base_vierge
    scenario = ScenarioAleas()
    scenario.reglages[HORLOGE_DECALEE]["probabilite"] = 1.0
    scenario.reglages[HORLOGE_DECALEE]["amplitude_heures"] = 240

    passage = PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, None, scenario,
    )
    depart = passage.simulated_at
    await passage.appliquer_aleas_initiaux()

    assert passage.simulated_at != depart


async def test_la_memoire_retenue_est_rendue_a_la_fin(base_vierge):
    del base_vierge
    scenario = ScenarioAleas()
    scenario.reglages["SATURATION_MEMOIRE"]["probabilite"] = 1.0
    scenario.reglages["SATURATION_MEMOIRE"]["megaoctets"] = 1

    passage = PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7, None, scenario,
    )
    await passage.run()

    assert passage.memoire_retenue is None


# ── S5 : les profils des cinq types ──────────────────────────────────────

def test_les_cinq_types_sont_au_catalogue():
    assert set(PROFILS) == {LIBRE, QUALITE, MDM, ENTREPOT, GOUVERNANCE}


def test_un_type_inconnu_retombe_sur_la_qualite():
    assert profil(None).code == QUALITE
    assert profil("PAS_UN_TYPE").code == QUALITE
    assert profil("entrepot").code == ENTREPOT


def test_le_profil_entrepot_vise_le_volume():
    """Le volume est ce qui distingue ce type des trois autres."""

    entrepot = PROFILS[ENTREPOT]
    qualite = PROFILS[QUALITE]

    assert entrepot.passages_simultanes_max > qualite.passages_simultanes_max
    assert entrepot.vitesse > qualite.vitesse


def test_aucun_type_ne_declenche_d_alea_de_lui_meme():
    """Un crash test est un geste délibéré, jamais un réglage d'usine.

    Un aléa qui frappe sans qu'on l'ait demandé rend l'exécution illisible :
    on ne sait plus si une incohérence vient de là ou d'ailleurs.
    """

    for profil_simulation in PROFILS.values():
        assert profil_simulation.aleas == {}, profil_simulation.code


def test_le_profil_qualite_injecte_plus_que_l_entrepot():
    taux_qualite = PROFILS[QUALITE].anomalies[MONTANT_ABERRANT]["taux"]
    taux_entrepot = PROFILS[ENTREPOT].anomalies[MONTANT_ABERRANT]["taux"]

    assert taux_qualite > taux_entrepot


def test_le_profil_gouvernance_fait_entrer_les_anomalies_en_cours_de_route():
    reglage = PROFILS[GOUVERNANCE].anomalies[MONTANT_ABERRANT]

    assert reglage["declenchement"] == DECLENCHEMENT_DIFFERE
    assert reglage["delai_secondes"] > 0


def test_aucun_type_ne_prepare_rien_en_attendant_le_cahier_des_charges():
    """Tant que les moteurs T1-T4 n'existent pas, aucune préparation ne tourne."""

    for profil_simulation in PROFILS.values():
        assert profil_simulation.preparation == {}, profil_simulation.code


def test_le_mode_libre_part_vierge():
    """Le bac à sable ne pré-configure rien : tout se compose à la main."""

    libre = PROFILS[LIBRE]
    assert libre.anomalies == {}
    assert libre.aleas == {}
    assert libre.preparation == {}


def test_un_alea_declenche_a_la_main_frappe_malgre_une_probabilite_nulle():
    """C'est tout le mécanisme du poste de pilotage : l'ordre l'emporte."""

    scenario = ScenarioAleas()
    assert scenario.reglage(RAFALE, "probabilite", 0.0) == 0.0

    scenario.armer(RAFALE)

    assert scenario.frappe(RAFALE, random.Random(1)) is True


def test_le_profil_regle_la_configuration_du_moteur():
    config_moteur = PROFILS[ENTREPOT].config_moteur()

    assert config_moteur.default_speed == PROFILS[ENTREPOT].vitesse
    assert config_moteur.max_concurrent_passages == PROFILS[ENTREPOT].passages_simultanes_max
