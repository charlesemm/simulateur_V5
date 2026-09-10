from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import date, datetime, timedelta, timezone
import unicodedata
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from faker import Faker
from sqlalchemy import  func, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_factory
from app.models import (
    Agent, CenterHealthAgent, Country, Department, HealthCenter,
    HealthProfessional, HealthProfessionalCenter,
    HealthProfessionalMedicalSpecialty, InsuredBirthInfo, InsuredIdentifier,
    InsuredPerson, InsuredProfession, InsuredRight, Locality, MedicalAct,
    MedicalSpecialty, Medication, Pathology, Regime, Region, TypeInvoice,
)

from seed.constants import (
    COUNTRIES, HEALTH_CENTER_TYPES, INVOICE_TYPES, IVORIAN_CITIES,
    IVORIAN_DISTRICTS, IVORIAN_FIRST_NAMES, IVORIAN_LAST_NAMES, MEDICAL_ACTS,
    MEDICAL_SPECIALTIES, MEDICATION_SEEDS, PATHOLOGY_LABELS, PROFESSIONS,
)
from anomalies import anomalies_config, apply_anomalies_to_row
from anomalies.repository import enregistrer_injections

# Carnet des anomalies posées par le seed. Elles corrompent le référentiel
# avant qu'aucune exécution n'existe : leur SIMULATION_ID reste nul.
anomalies_seed = anomalies_config.contexte()

## initialisation du logger
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

## initialialisation du faker
RANDOM_SEED = 225
VALID_FROM = date(2026,8, 17)

# Les tables historisées veulent un horodatage, pas une date : on fige le
# même instant partout pour que le seed reste reproductible.
VALID_FROM_TS = datetime.combine(VALID_FROM, datetime.min.time(), tzinfo=timezone.utc)

# Part des assurés disposant de droits ouverts. Les volumes réels du système
# CNAM suggèrent une proportion bien plus faible, mais un simulateur qui
# rejette presque tous les passages ne démontre rien.
#
# Le chiffre est une hypothèse assumée, consignée dans seed/provenance.py et
# exposée par la gouvernance. La variable d'environnement permet de l'ajuster
# le jour où les vrais volumes seront connus, sans toucher au code.
def _taux_couverture() -> float:
    """Lit le taux de couverture, en le bornant à un intervalle sensé."""

    try:
        valeur = float(os.getenv("TAUX_COUVERTURE", "0.60"))
    except ValueError:
        return 0.60
    return max(0.0, min(1.0, valeur))


TAUX_COUVERTURE = _taux_couverture()
ANNEE_DROITS = 2026
random_generator = random.Random(RANDOM_SEED)
fake = Faker("fr_FR")
Faker.seed(RANDOM_SEED)

""" fonction pour creer une chaine ascii utilisable dasn courriel synthetique """
def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))

def calculate_ean13(prefix: str) -> str:
    """Calcule le chiffre de contrôle d'un préfixe EAN à douze chiffres."""

    digits = [int(character) for character in prefix.zfill(12)[-12:]]
    checksum = (10 - sum(value * (1 if index % 2 == 0 else 3) for index, value in enumerate(digits)) % 10) % 10
    return "".join(map(str, digits)) + str(checksum)


async def upsert_rows(
        session: AsyncSession,
        model: type,
        rows: list[dict[str, Any]],
        batch_size: int = 500,
) -> None:
    """Insère un lot ou met à jour les lignes portant la même clé primaire.

    Découpe automatiquement en petits lots pour éviter la limite asyncpg de 32767 paramètres.
    """

    if not rows:
        return

    # Le mapping traduit les attributs Python vers les noms physiques TB_XXX.
    mapper = inspect(model)
    attribute_to_column = {
        property_.key: property_.columns[0].name for property_ in mapper.column_attrs
    }

    table = model.__table__
    total_batches = (len(rows) + batch_size - 1) // batch_size

    # Boucler sur chaque lot
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(rows))
        batch = rows[start_idx:end_idx]

        # Convertir les attributs Python en noms physiques pour ce lot
        physical_rows = [
            {attribute_to_column[key]: value for key, value in row.items()}
            for row in batch
        ]

        statement = insert(table).values(physical_rows)

        # La création reste intacte ; seuls les champs métier et l'audit de
        # modification changent lors d'un second lancement.
        update_values: dict[str, Any] = {}
        for column in table.columns:
            if column.primary_key or column.name in {
                "DATE_CREATION", "UTILISATEUR_ID_CREATION"
            }:
                continue
            if column.name == "DATE_MODIFICATION":
                update_values[column.name] = func.now()
            elif column.name == "UTILISATEUR_ID_MODIFICATION":
                update_values[column.name] = "seed.py"
            else:
                update_values[column.name] = statement.excluded[column.name]

        statement = statement.on_conflict_do_update(
            index_elements=list(table.primary_key.columns),
            set_=update_values,
        )
        await session.execute(statement)
        logger.info(
            "Lot %d/%d : %d lignes upsertées pour %s.",
            batch_idx + 1,
            total_batches,
            len(batch),
            table.name
        )


def audit_values() -> dict[str, str]:
    """Retourne l'identifiant d'audit commun aux insertions du seed."""

    return {"utilisateur_id_creation": "seed.py"}

def centre_sante_code(rang: int) -> str:
    """Produit un code de centre entier pur, sur sept caractères.

    Aucune lettre : seul `numero_securite_sociale` ci-dessous a un motif
    similaire à respecter, mais ici c'est un simple rang aligné à zéro.
    """

    return f"{rang:07d}"


def build_health_centers() -> list[dict[str, Any]]:
    """Construit trente centres variés répartis dans quinze localités."""

    rows = []
    for index in range(30):
        type_code, type_label = HEALTH_CENTER_TYPES[index % len(HEALTH_CENTER_TYPES)]
        city = IVORIAN_CITIES[index % len(IVORIAN_CITIES)]
        rows.append({
            "centre_sante_code": centre_sante_code(index + 1),
            "collectivite_code": f"COL{index % 15 + 1:02d}",
            "type_etablissement_sanitaire_code": type_code,
            "centre_sante_numero_immatriculation": f"CI-CMU-{index + 1:05d}",
            "centre_sante_denomination": f"{type_label} de {city}",
            **audit_values(),
        })
    return rows

def synthetic_identity(index: int) -> tuple[str, str]:
    """Mélange de façon déterministe noms ivoiriens et prénoms Faker."""

    last_name = IVORIAN_LAST_NAMES[index % len(IVORIAN_LAST_NAMES)]
    first_name = (
        IVORIAN_FIRST_NAMES[index % len(IVORIAN_FIRST_NAMES)]
        if index % 3 != 0 else fake.first_name()
    )
    return last_name, first_name

def build_agents() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Crée cinquante agents d'accueil affectés et dix médecins conseils centraux."""

    agents, assignments = [], []
    for index in range(60):
        last_name, first_name = synthetic_identity(index)
        agent_code = f"AG{index + 1:03d}"
        agent_type = "accueil" if index < 50 else "medecin_conseil"
        email_root = normalize_text(f"{first_name}.{last_name}").lower().replace("'", "")
        
        # Créer le dict de l'agent
        agent_row = {
            "agent_code": agent_code,
            "agent_code_gestion": f"GEST{index + 1:04d}",
            "agent_prenoms": first_name,
            "agent_nom": last_name,
            "agent_email": f"{email_root}.{index + 1}@cmu.demo.ci",
            "agent_type_code": agent_type,
            **audit_values(),
        }
        
        # Appliquer les anomalies
        agent_row = apply_anomalies_to_row(agent_row, anomalies_seed, "agent")
        
        # Ajouter à la liste
        agents.append(agent_row)
        
        # Les médecins conseils appartiennent au niveau central et ne reçoivent
        # donc volontairement aucune affectation géographique.
        if agent_type == "accueil":
            assignments.append({
                "centre_sante_code": centre_sante_code(index % 30 + 1),
                "agent_code": agent_code,
                "date_debut": VALID_FROM,
                "date_fin": None,
                **audit_values(),
            })
    return agents, assignments

# Le multiplicateur est impair et non divisible par cinq : il n'a donc aucun
# diviseur commun avec le modulo, ce qui fait de la transformation une
# bijection. Deux assurés ne peuvent mathématiquement pas partager un numéro.
SECU_MULTIPLICATEUR = 3_141_592_653
SECU_DECALAGE = 2_718_281_829
SECU_MODULO = 10 ** 10


def numero_securite_sociale(index: int) -> str:
    """Produit un numéro de treize caractères commençant par 394.

    Les dix chiffres suivants paraissent tirés au hasard mais restent uniques
    et stables : un même index redonne toujours le même numéro, et augmenter
    le nombre d'assurés ne redistribue pas ceux qui existent déjà.
    """

    suffixe = (SECU_MULTIPLICATEUR * index + SECU_DECALAGE) % SECU_MODULO
    return f"394{suffixe:010d}"

# Le régime n'est pas un attribut propre de l'assuré : il découle de ce qu'il
# fait. Cette table de correspondance est la seule source de vérité, et elle
# est lue aussi bien par l'assuré que par sa ligne de profession.
PROFESSION_REGIME = {code: regime for code, _, regime in PROFESSIONS}


def insured_profession(index: int) -> str:
    """Tire la profession d'un assuré, de façon stable et indépendante.

    Son générateur dédié garantit qu'ajouter des assurés ne redistribue pas
    les professions -- ni, par conséquent, les régimes qui en découlent.
    """

    generator = random.Random(RANDOM_SEED + 20_000 + index)
    return generator.choice([code for code, _, _ in PROFESSIONS])


def insured_profile(index: int) -> tuple[date, str]:
    """Tire la date de naissance et déduit le régime de la profession.

    Chaque assuré possède son propre générateur dérivé de son index : ses
    attributs ne dépendent donc pas de l'ordre de la boucle, et un futur
    changement dans la génération ne redistribuera pas les régimes.
    """

    generator = random.Random(RANDOM_SEED + index)
    age_en_jours = generator.randint(365, 95 * 365)
    date_naissance = VALID_FROM - timedelta(days=age_en_jours)
    return date_naissance, PROFESSION_REGIME[insured_profession(index)]

def build_insured_people() -> list[dict[str, Any]]:
    """Crée cent mille assurés aux identifiants stables et non séquentiels."""

    rows = []
    for index in range(100000):
        last_name, first_name = synthetic_identity(index + 100)
        date_naissance, regime = insured_profile(index)
        insured_row = {
            "personne_uuid": uuid5(NAMESPACE_URL, f"cmu-demo-assure-{index + 1}"),
            "numero_recepisse": f"REC-{2026}-{index + 1:06d}",
            "assure_numero_identifiant": f"CMU{index + 1:010d}",
            "numero_secu": numero_securite_sociale(index),
            "civilite_code": "MME" if index % 2 == 0 else "M",
            "assure_nom": last_name,
            "assure_prenoms": first_name,
            "assure_nom_patronymique": last_name if index % 5 else f"{last_name}-{first_name}",
            "assure_date_naissance": date_naissance,
            "regime_code": regime,
            **audit_values(),
        }

        # Appliquer les anomalies
        insured_row = apply_anomalies_to_row(insured_row, anomalies_seed, "insured")
        rows.append(insured_row)
    return rows

def build_professionals() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Crée cent médecins, cinquante infirmiers et leurs affectations."""

    professionals, specialties, centers = [], [], []
    for index in range(150):
        last_name, first_name = synthetic_identity(index + 300)
        code = f"PS{index + 1:04d}"
        is_physician = index < 100
        professionals.append({
            "professionnel_sante_code": code,
            "nom": last_name,
            "prenoms": first_name,
            "type_code": "medecin" if is_physician else "infirmier",
            "numero_ordre": f"OMCI-{index + 1:06d}" if is_physician else f"ONICI-{index + 1:06d}",
            "statut": "actif",
            **audit_values(),
        })
        centers.append({
            "professionnel_sante_code": code,
            "centre_sante_code": centre_sante_code(index % 30 + 1),
            "date_debut": VALID_FROM,
            "date_fin": None,
            **audit_values(),
        })
        if is_physician:
            specialties.append({
                "professionnel_sante_code": code,
                "specialite_medicale_code": MEDICAL_SPECIALTIES[index % len(MEDICAL_SPECIALTIES)][0],
                "date_debut": VALID_FROM,
                "date_fin": None,
                **audit_values(),
            })
    return professionals, specialties, centers

def build_pathologies() -> list[dict[str, Any]]:
    """Transforme les cent libellés en codes alphanumériques de trois caractères."""

    return [
        {
            "pathologie_code": f"{chr(65 + index // 10)}{index % 10 + 1:02d}",
            "pathologie_date_debut": VALID_FROM,
            "sous_chapitre_code": f"CH{index // 10 + 1:02d}",
            "pathologie_denomination": label,
            "pathologie_date_fin": None,
            "pathologie_statut": "actif",
            **audit_values(),
        }
        for index, label in enumerate(PATHOLOGY_LABELS)
    ]

def build_medications() -> list[dict[str, Any]]:
    """Décline cinquante molécules en deux cents présentations crédibles."""

    rows = []
    for molecule_index, (name, dci, presentations, base_tariff) in enumerate(MEDICATION_SEEDS):
        for presentation_index, presentation in enumerate(presentations):
            index = molecule_index * 4 + presentation_index
            rows.append({
                "medicament_code": f"MED{index + 1:04d}",
                "medicament_date_debut": VALID_FROM,
                "type_code": "GEN",
                "medicament_denomination": f"{name} {presentation}",
                "medicament_ean13": calculate_ean13(f"618000{index + 1:06d}"),
                "dci_code": dci,
                "laboratoire_code": f"LAB{index % 12 + 1:02d}",
                "famille_forme_code": "FORME",
                "conditionnement_code": f"COND{presentation_index + 1}",
                "presentation_code": f"PRE{presentation_index + 1}",
                "liste_types_factures": "PHA",
                "liste_genres": "M,F",
                "medicament_quantite_maximum": 3,
                "medicament_age_minimum": 0,
                "medicament_age_maximum": 120,
                "medicament_hapax_statut": False,
                "medicament_tarif_default": Decimal(base_tariff + presentation_index * 250),
                "medicament_statut": "actif",
                "medicament_date_fin": None,
                **audit_values(),
            })
    return rows

def build_medical_acts() -> list[dict[str, Any]]:
    """Construit les actes avec leurs types de factures autorisés."""

    return [
        {
            "acte_medical_code": code,
            "acte_medical_date_debut": VALID_FROM,
            "article_code": f"ART{index + 1:03d}",
            "acte_medical_type": act_type,
            "acte_medical_denomination": label,
            "liste_types_factures": invoice_types,
            "liste_genres": "M,F",
            "acte_medical_age_minimum": 0,
            "acte_medical_age_maximum": 120,
            "acte_medical_quantite_maximum": 5,
            "acte_medical_hapax_statut": False,
            "acte_medical_statut": "actif",
            "acte_medical_date_fin": None,
            **audit_values(),
        }
        for index, (code, label, act_type, invoice_types, tariff) in enumerate(MEDICAL_ACTS)
    ]


def build_regimes() -> list[dict[str, Any]]:
    """Reprend les deux régimes réels et leurs taux de remboursement."""

    return [
        {
            "regime_code": code, "regime_date_debut": VALID_FROM_TS,
            "regime_code_parent": "RGB", "regime_denomination": libelle,
            "regime_taux": Decimal(taux), "regime_date_fin": None,
            "regime_statut": 1, **audit_values(),
        }
        for code, libelle, taux in (
            ("RAM", "RÉGIME D'ASSISTANCE MÉDICALE", 100),
            ("RGB", "RÉGIME GÉNÉRAL DE BASE", 70),
        )
    ]

def build_countries() -> list[dict[str, Any]]:
    """Crée les pays de naissance plausibles pour une population ivoirienne."""

    return [
        {
            "continent_code": continent, "pays_code": code,
            "pays_date_debut": VALID_FROM_TS, "pays_code_numerique": numerique,
            "pays_denomination": denomination, "pays_gentile": gentile,
            "pays_indicatif": indicatif, "pays_drapeau": f"{code.lower()}.svg",
            "devise_code": devise, "pays_date_fin": None, "pays_statut": 1,
            "pays_latitude": Decimal(str(latitude)),
            "pays_longitude": Decimal(str(longitude)),
            **audit_values(),
        }
        for (code, continent, numerique, denomination, gentile, indicatif,
             devise, latitude, longitude) in COUNTRIES
    ]

def build_localisation() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Décline les districts en départements puis en localités.

    Le code de chaque niveau préfixe celui du niveau suivant, ce qui rend la
    hiérarchie lisible sans jointure : CIV -> CIV001 -> CIV0011 -> CIV00111.
    """

    regions, departments, localities = [], [], []

    for district_index, (nom, latitude, longitude) in enumerate(IVORIAN_DISTRICTS):
        region_code = f"CIV{district_index + 1:03d}"
        regions.append({
            "pays_code": "CIV", "region_type": "D", "region_code": region_code,
            "region_date_debut": VALID_FROM_TS, "region_denomination": nom,
            "region_date_fin": None, "region_statut": 1,
            "region_latitude": Decimal(str(latitude)),
            "region_longitude": Decimal(str(longitude)),
            **audit_values(),
        })

        # Chaque district reçoit deux départements, chaque département quatre
        # localités : cent douze localités au total, de quoi peupler une carte.
        for department_index in range(2):
            department_code = f"{region_code}{department_index + 1}"
            departments.append({
                "region_code": region_code, "departement_type": "P",
                "departement_code": department_code,
                "departement_date_debut": VALID_FROM_TS,
                "departement_denomination": f"{nom} {department_index + 1}",
                "departement_date_fin": None, "departement_statut": 1,
                "departement_latitude": Decimal(str(round(latitude + department_index * 0.25, 6))),
                "departement_longitude": Decimal(str(round(longitude - department_index * 0.25, 6))),
                **audit_values(),
            })

            for locality_index in range(4):
                localities.append({
                    "departement_code": department_code, "localite_type": "S",
                    "localite_code": f"{department_code}{locality_index + 1}",
                    "localite_date_debut": VALID_FROM_TS,
                    "localite_denomination": IVORIAN_CITIES[
                        (district_index * 8 + department_index * 4 + locality_index)
                        % len(IVORIAN_CITIES)
                    ],
                    "localite_date_fin": None, "localite_statut": 1,
                    "localite_latitude": Decimal(str(round(latitude + locality_index * 0.1, 6))),
                    "localite_longitude": Decimal(str(round(longitude - locality_index * 0.1, 6))),
                    **audit_values(),
                })

    return regions, departments, localities

def build_insured_identifiers(assures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Historise le numéro de sécurité sociale et, parfois, une pièce d'identité.

    Le numéro déjà porté par l'assuré devient une ligne de type NNI : c'est
    lui qui restera la référence, les autres types ne font que l'accompagner.
    """

    rows = []
    for index, assure in enumerate(assures):
        generator = random.Random(RANDOM_SEED + 10_000 + index)
        rows.append({
            "personne_uuid": assure["personne_uuid"],
            "type_identifiant_code": "NNI",
            "identifiant_date_debut": VALID_FROM_TS,
            "identifiant_numero": assure["numero_secu"],
            "identifiant_date_fin": None,
            **audit_values(),
        })
        rows.append({
            "personne_uuid": assure["personne_uuid"],
            "type_identifiant_code": "RECEP",
            "identifiant_date_debut": VALID_FROM_TS,
            "identifiant_numero": assure["numero_recepisse"],
            "identifiant_date_fin": None,
            **audit_values(),
        })
        # Trois assurés sur dix présentent en plus une pièce d'identité.
        if generator.random() < 0.30:
            type_code = generator.choice(["CNI", "PASSPT", "ATTEST"])
            rows.append({
                "personne_uuid": assure["personne_uuid"],
                "type_identifiant_code": type_code,
                "identifiant_date_debut": VALID_FROM_TS,
                "identifiant_numero": f"{type_code}{generator.randrange(10 ** 9):09d}",
                "identifiant_date_fin": None,
                **audit_values(),
            })
    return rows

def build_insured_professions(assures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persiste la profession dont l'assuré tire déjà son régime.

    C'est la profession qui commande : `insured_profile` en déduit le régime
    porté par l'assuré. Les deux lectures ne peuvent donc pas diverger.
    """

    rows = []
    for index, assure in enumerate(assures):
        rows.append({
            "personne_uuid": assure["personne_uuid"],
            "profession_code": insured_profession(index),
            "profession_date_debut": VALID_FROM_TS,
            "profession_date_fin": None,
            **audit_values(),
        })
    return rows

def build_insured_birth_infos(assures: list[dict[str, Any]],
                              localities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rattache chaque assuré à une localité de naissance.

    Un assuré sur vingt est né hors de Côte d'Ivoire : ses codes régionaux
    restent nuls, seul le pays est renseigné -- exactement ce que permet la
    table d'origine.
    """

    etrangers = [pays[0] for pays in COUNTRIES if pays[0] != "CIV"]
    rows = []
    for index, assure in enumerate(assures):
        generator = random.Random(RANDOM_SEED + 30_000 + index)
        if generator.random() < 0.05:
            ligne = {
                "pays_code": generator.choice(etrangers), "region_code": None,
                "departement_code": None, "localite_code": None,
                "code_postal": None, "naissance_lieu": None,
            }
        else:
            localite = localities[generator.randrange(len(localities))]
            departement_code = localite["departement_code"]
            ligne = {
                "pays_code": "CIV",
                "region_code": departement_code[:6],
                "departement_code": departement_code,
                "localite_code": localite["localite_code"],
                "code_postal": f"{generator.randrange(1000, 99999):05d}",
                "naissance_lieu": localite["localite_denomination"],
            }
        rows.append({
            "personne_uuid": assure["personne_uuid"],
            "naissance_date_debut": VALID_FROM_TS,
            "naissance_date_fin": None,
            **ligne,
            **audit_values(),
        })
    return rows

def build_insured_rights(assures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ouvre les droits mois par mois pour la part couverte de la population.

    Un assuré couvert l'est rarement toute l'année : on ferme quelques mois
    au hasard, ce qui donnera au moteur de vraies occasions de rejeter une
    facture pour droits fermés.
    """

    rows = []
    for index, assure in enumerate(assures):
        generator = random.Random(RANDOM_SEED + 40_000 + index)
        if generator.random() >= TAUX_COUVERTURE:
            continue

        # Entre zéro et trois mois fermés dans l'année, tirés sans remise.
        mois_fermes = set(generator.sample(range(1, 13), generator.randint(0, 3)))
        for mois in range(1, 13):
            debut = datetime(ANNEE_DROITS, mois, 1, tzinfo=timezone.utc)
            fin = (
                datetime(ANNEE_DROITS + 1, 1, 1, tzinfo=timezone.utc)
                if mois == 12
                else datetime(ANNEE_DROITS, mois + 1, 1, tzinfo=timezone.utc)
            )
            rows.append({
                "personne_uuid": assure["personne_uuid"],
                "droits_annee": ANNEE_DROITS,
                "droits_mois": mois,
                "droits_id": f"DRT-{ANNEE_DROITS}{mois:02d}-{index + 1:08d}",
                "droits_statut": 0 if mois in mois_fermes else 1,
                "droits_date_debut": debut,
                "droits_date_fin": fin - timedelta(seconds=1),
                **audit_values(),
            })
    return rows

async def seed_database() -> None:
    """Peuple toutes les tables référentielles dans une transaction unique."""

    logger.info("Démarrage du peuplement référentiel CMU.")
    agents, agent_assignments = build_agents()
    professionals, professional_specialties, professional_centers = build_professionals()
    regions, departments, localities = build_localisation()
    datasets = {
        "assures": build_insured_people(), "centres": build_health_centers(),
        "agents": agents, "affectations_agents": agent_assignments,
        "professionnels": professionals, "specialites_professionnels": professional_specialties,
        "centres_professionnels": professional_centers, "pathologies": build_pathologies(),
        "medicaments": build_medications(), "actes": build_medical_acts(),
    }
    expected = {"assures": 100000, "centres": 30, "agents": 60, "affectations_agents": 50,
                "professionnels": 150, "specialites_professionnels": 100,
                "centres_professionnels": 150, "pathologies": 100,
                "medicaments": 200, "actes": 30}
    assert all(len(datasets[key]) == value for key, value in expected.items()), "Volumétrie invalide."

    specialties = [{"specialite_medicale_code": code, "denomination": label, **audit_values()}
                    for code, label in MEDICAL_SPECIALTIES]
    invoice_types = [{"type_facture_code": code, "type_facture_date_debut": VALID_FROM,
                      "type_facture_denomination": label, "type_facture_date_fin": None,
                      "type_facture_statut": "actif", **audit_values()}
                     for code, label in INVOICE_TYPES]

    async with async_session_factory() as session:
        async with session.begin():
            # Les référentiels de valeurs d'abord : les satellites de l'assuré
            # s'y rattachent par leurs codes.
            await upsert_rows(session, Regime, build_regimes())
            await upsert_rows(session, Country, build_countries())
            await upsert_rows(session, Region, regions)
            await upsert_rows(session, Department, departments)
            await upsert_rows(session, Locality, localities)

            await upsert_rows(session, InsuredPerson, datasets["assures"])
            await upsert_rows(session, HealthCenter, datasets["centres"])
            await upsert_rows(session, Agent, datasets["agents"])
            await upsert_rows(session, MedicalSpecialty, specialties)
            await upsert_rows(session, HealthProfessional, datasets["professionnels"])
            await upsert_rows(session, Pathology, datasets["pathologies"])
            await upsert_rows(session, Medication, datasets["medicaments"])
            await upsert_rows(session, MedicalAct, datasets["actes"])
            await upsert_rows(session, TypeInvoice, invoice_types)
            await upsert_rows(session, CenterHealthAgent, datasets["affectations_agents"])
            await upsert_rows(session, HealthProfessionalMedicalSpecialty, datasets["specialites_professionnels"])
            await upsert_rows(session, HealthProfessionalCenter, datasets["centres_professionnels"])

            # En dernier : ces quatre tables portent une clé étrangère vers
            # l'assuré, qui doit donc déjà être inséré.
            assures = datasets["assures"]
            await upsert_rows(session, InsuredIdentifier, build_insured_identifiers(assures))
            await upsert_rows(session, InsuredProfession, build_insured_professions(assures))
            await upsert_rows(session, InsuredBirthInfo, build_insured_birth_infos(assures, localities))
            await upsert_rows(session, InsuredRight, build_insured_rights(assures))

            # Le journal part dans la même transaction que les lignes qu'il
            # décrit : un seed annulé n'y laisse aucune anomalie fantôme.
            posees = await enregistrer_injections(anomalies_seed.vider(), session)
    if posees:
        logger.info("Anomalies consignées au journal : %s.", posees)
    logger.info("Peuplement référentiel terminé avec succès.")

def main() -> None:
    """Lance le seed et présente une erreur française en cas d'échec."""

    try:
        asyncio.run(seed_database())
    except Exception:
        logger.exception("Le peuplement référentiel a échoué ; la transaction est annulée.")
        raise
