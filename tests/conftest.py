"""Fixtures communes : base de test isolée et référentiel minimal.

La base de test est **toujours** distincte de la base de travail : le nom de
la base porte le suffixe « _test » et la suite refuse de démarrer si les deux
URL coïncident. Les tests tronquent les tables entre chaque cas, une erreur de
configuration effacerait donc des données réelles.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from dotenv import load_dotenv

load_dotenv()

SUFFIXE_TEST = "_test"


def _url_de_test() -> str:
    """Dérive l'URL de la base de test, ou lit celle fournie explicitement."""

    explicite = os.getenv("TEST_DATABASE_URL")
    if explicite:
        return explicite

    travail = os.getenv("DATABASE_URL")
    if not travail:
        raise RuntimeError(
            "DATABASE_URL est absente : impossible de déduire la base de test."
        )
    # Le nom de la base est le dernier segment du chemin, avant d'éventuels
    # paramètres de connexion.
    #
    # La dérivation doit rester idempotente : ce module réécrit DATABASE_URL,
    # et une seconde évaluation repartirait d'une URL déjà suffixée. Elle
    # produirait alors « ..._test_test », un nom de base qui n'existe pas.
    return re.sub(
        rf"/([^/?]+?)(?:{re.escape(SUFFIXE_TEST)})?(\?|$)",
        rf"/\1{SUFFIXE_TEST}\2",
        travail,
        count=1,
    )


URL_TEST = _url_de_test()
URL_TRAVAIL = os.getenv("DATABASE_URL")

if URL_TEST == URL_TRAVAIL:
    raise RuntimeError(
        "La base de test est identique à la base de travail. "
        "Définis TEST_DATABASE_URL pour les séparer avant de lancer la suite."
    )

# Doit être posé avant tout import applicatif : app.database construit son
# moteur au moment de l'import, à partir de cette variable.
os.environ["DATABASE_URL"] = URL_TEST

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    Agent, HealthCenter, HealthProfessional, InsuredBirthInfo,
    InsuredIdentifier, InsuredPerson, InsuredProfession, InsuredRight,
    MedicalAct, Medication, Pathology, Regime,
)
from anomalies.catalogue import CATALOGUE_INITIAL, CODES  # noqa: E402
from anomalies.models import AnomalyType  # noqa: E402
from auth.models import User  # noqa: E402
from auth.security import hash_password  # noqa: E402
from seed.constants import MEDICAL_ACTS  # noqa: E402

VALIDITE = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Deux assurés suffisent à couvrir les deux régimes et les deux états de
# droits : c'est le plus petit jeu qui exerce toutes les branches du moteur.
ASSURE_COUVERT = uuid.UUID("11111111-1111-5111-8111-111111111111")
ASSURE_SANS_DROITS = uuid.UUID("22222222-2222-5222-8222-222222222222")


@pytest.fixture(scope="session")
def base_de_test():
    """Applique les migrations sur la base de test, une fois pour la suite."""

    from alembic import command
    from alembic.config import Config

    # C'est DATABASE_URL, posée plus haut sur URL_TEST, qui décide de la base
    # migrée : alembic/env.py l'impose et écraserait toute autre valeur donnée
    # ici. La ligne ci-dessous ne fait que garder le fichier INI cohérent.
    configuration = Config("alembic.ini")
    configuration.set_main_option("sqlalchemy.url", URL_TEST)
    command.upgrade(configuration, "head")
    return URL_TEST


@pytest.fixture
async def base_vierge(base_de_test):
    """Vide les tables métier et réinstalle le référentiel minimal.

    Le moteur et l'API ouvrent leurs propres sessions : une transaction
    annulée en fin de test ne les isolerait pas. On repart donc d'une base
    nettoyée avant chaque cas.
    """

    del base_de_test
    moteur = create_async_engine(URL_TEST)
    async with moteur.begin() as connexion:
        tables = [ligne[0] for ligne in (await connexion.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename LIKE 'TB\\_%'"
        ))).all()]
        if tables:
            liste = ", ".join(f'"{nom}"' for nom in tables)
            await connexion.execute(text(f"TRUNCATE {liste} RESTART IDENTITY CASCADE"))
    await moteur.dispose()

    # La configuration des anomalies est un singleton de processus : sans
    # remise à zéro, un test qui coupe un type le couperait pour les suivants.
    from anomalies.config import Reglage, anomalies_config

    anomalies_config.enabled = False
    anomalies_config.rate = 0.0
    anomalies_config.injected_count = 0
    anomalies_config.reglages = {code: Reglage() for code in CODES}
    anomalies_config.debut_execution = None

    await _installer_referentiel()
    yield


async def _installer_referentiel() -> None:
    """Insère le plus petit référentiel qui permette un parcours complet."""

    audit = {"utilisateur_id_creation": "tests"}
    mois = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        # Le catalogue d'anomalies est un référentiel comme les autres : le
        # TRUNCATE l'emporte, et le journal des injections y renvoie.
        session.add_all([
            AnomalyType(
                anomalie_code=type_anomalie.code,
                anomalie_libelle=type_anomalie.libelle,
                anomalie_famille=type_anomalie.famille,
                anomalie_couleur=type_anomalie.couleur,
                anomalie_declenchement="continu",
                anomalie_table_cible=type_anomalie.table_cible,
                anomalie_colonne_cible=type_anomalie.colonne_cible,
                anomalie_severite=type_anomalie.severite,
                anomalie_active=True,
                anomalie_taux=Decimal("0.00"),
                **audit,
            )
            for type_anomalie in CATALOGUE_INITIAL
        ])
        session.add_all([
            Regime(regime_code="RGB", regime_date_debut=VALIDITE, regime_code_parent="RGB",
                   regime_denomination="RÉGIME GÉNÉRAL DE BASE", regime_taux=Decimal("70"),
                   regime_statut=1, **audit),
            Regime(regime_code="RAM", regime_date_debut=VALIDITE, regime_code_parent="RGB",
                   regime_denomination="RÉGIME D'ASSISTANCE MÉDICALE", regime_taux=Decimal("100"),
                   regime_statut=1, **audit),

            HealthCenter(centre_sante_code="CS001",
                         centre_sante_numero_immatriculation="IMM001",
                         centre_sante_denomination="Centre de santé de test",
                         type_etablissement_sanitaire_code="CSU", **audit),
            HealthProfessional(professionnel_sante_code="PS0001", nom="Koné",
                               prenoms="Awa", type_code="medecin", statut="actif", **audit),
            Agent(agent_code="AG0001", agent_prenoms="Yao", agent_nom="Brou",
                  agent_email="yao.brou@cnam.ci", agent_type_code="medecin_conseil", **audit),

            Pathology(pathologie_code="P01", pathologie_date_debut=date(2026, 1, 1),
                      pathologie_denomination="Paludisme simple", pathologie_statut="actif", **audit),
            Pathology(pathologie_code="P02", pathologie_date_debut=date(2026, 1, 1),
                      pathologie_denomination="Angine aiguë", pathologie_statut="actif", **audit),
            Pathology(pathologie_code="P03", pathologie_date_debut=date(2026, 1, 1),
                      pathologie_denomination="Gastrite", pathologie_statut="actif", **audit),

            Medication(medicament_code="MED0001", medicament_date_debut=date(2026, 1, 1),
                       medicament_denomination="Paracétamol 500 mg",
                       medicament_tarif_default=Decimal("500"),
                       medicament_statut="actif", **audit),

            # Le catalogue complet, pas quelques codes choisis : le moteur
            # pioche désormais dans tout MEDICAL_ACTS pour la prestation
            # principale (simulation/passage.py), un sous-ensemble laisserait
            # PRESTATION_ORPHELINE crier au loup sur des codes réels.
            *(MedicalAct(acte_medical_code=code, acte_medical_date_debut=date(2026, 1, 1),
                        acte_medical_type=famille, acte_medical_denomination=libelle,
                        acte_medical_tarif=Decimal(str(tarif)), acte_medical_statut="actif", **audit)
              for code, libelle, famille, _types_facture, tarif in MEDICAL_ACTS),

            InsuredPerson(personne_uuid=ASSURE_COUVERT, numero_secu="3840000000001",
                          assure_nom="Kouassi", assure_prenoms="Marie", civilite_code="MME",
                          assure_date_naissance=date(1990, 5, 12), regime_code="RGB",
                          numero_recepisse="REC-2026-000001",
                          assure_numero_identifiant="CMU0000000001", **audit),
            InsuredPerson(personne_uuid=ASSURE_SANS_DROITS, numero_secu="3840000000002",
                          assure_nom="Traoré", assure_prenoms="Ibrahim", civilite_code="M",
                          assure_date_naissance=date(1985, 3, 8), regime_code="RAM",
                          numero_recepisse="REC-2026-000002",
                          assure_numero_identifiant="CMU0000000002", **audit),
        ])
        await session.commit()

    async with async_session_factory() as session:
        # Seul le premier assuré a des droits, et seulement pour le mois en
        # cours : c'est ce qui permet de tester les deux issues de l'accueil.
        session.add_all([
            InsuredRight(personne_uuid=ASSURE_COUVERT, droits_annee=mois.year,
                         droits_mois=mois.month, droits_id="DRT-TEST-0001",
                         droits_statut=1, droits_date_debut=VALIDITE, **audit),
            InsuredRight(personne_uuid=ASSURE_SANS_DROITS, droits_annee=mois.year,
                         droits_mois=mois.month, droits_id="DRT-TEST-0002",
                         droits_statut=0, droits_date_debut=VALIDITE, **audit),
            InsuredProfession(personne_uuid=ASSURE_COUVERT, profession_code="SALPR",
                              profession_date_debut=VALIDITE, **audit),
            InsuredIdentifier(personne_uuid=ASSURE_COUVERT, type_identifiant_code="NNI",
                              identifiant_date_debut=VALIDITE,
                              identifiant_numero="3840000000001", **audit),
            InsuredBirthInfo(personne_uuid=ASSURE_COUVERT, naissance_date_debut=VALIDITE,
                             pays_code="CIV", naissance_lieu="Abidjan-Cocody", **audit),
        ])
        await session.commit()


@pytest.fixture
async def administrateur(base_vierge):
    """Crée un compte administrateur utilisable, mot de passe déjà choisi."""

    del base_vierge
    async with async_session_factory() as session:
        compte = User(
            utilisateur_uuid=uuid.uuid4(),
            email="admin@cnam.ci",
            nom_utilisateur="admin",
            mot_de_passe_hash=hash_password("MotDePasseAdmin1"),
            nom_complet="Administrateur de test",
            role="administrateur",
            statut_actif=True,
            doit_changer_mot_de_passe=False,
        )
        session.add(compte)
        await session.commit()
        await session.refresh(compte)
        return compte


@pytest.fixture
async def client_api(administrateur):
    """Ouvre un client HTTP sur l'application, authentifié en administrateur."""

    import httpx

    from api.main import fastapi_app
    from auth.security import create_access_token

    jeton = create_access_token(email=administrateur.email, role=administrateur.role)
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://tests",
        headers={"Authorization": f"Bearer {jeton}"},
    ) as client:
        yield client


async def compter(modele) -> int:
    """Compte les lignes d'une table, utilitaire des assertions."""

    from sqlalchemy import func

    async with async_session_factory() as session:
        return (await session.execute(
            select(func.count()).select_from(modele)
        )).scalar_one()


def dans_le_mois_courant() -> tuple[int, int]:
    """Retourne l'année et le mois courants, tels que le moteur les lit."""

    maintenant = datetime.now(timezone.utc)
    return maintenant.year, maintenant.month


__all__ = [
    "ASSURE_COUVERT", "ASSURE_SANS_DROITS", "URL_TEST", "VALIDITE",
    "compter", "dans_le_mois_courant", "timedelta",
]
