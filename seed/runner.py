from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
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
    Agent, CenterHealthAgent, HealthCenter, HealthProfessional,
    HealthProfessionalCenter, HealthProfessionalMedicalSpecialty,
    InsuredPerson, MedicalAct, MedicalSpecialty, Medication, Pathology,
    TypeInvoice,
)

from seed.constants import (
    HEALTH_CENTER_TYPES, INVOICE_TYPES, IVORIAN_CITIES,
    IVORIAN_FIRST_NAMES, IVORIAN_LAST_NAMES, MEDICAL_ACTS,
    MEDICAL_SPECIALTIES, MEDICATION_SEEDS, PATHOLOGY_LABELS,
)
from seed.anomalies import anomalies_config, apply_anomalies_to_row

## initialisation du logger
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

## initialialisation du faker
RANDOM_SEED = 225
VALID_FROM = date(2026,8, 17)
random_generator = random.Random(RANDOM_SEED)
fake = Faker("fr_FR")

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

def build_health_centers() -> list[dict[str, Any]]:
    """Construit trente centres variés répartis dans quinze localités."""

    rows = []
    for index in range(30):
        type_code, type_label = HEALTH_CENTER_TYPES[index % len(HEALTH_CENTER_TYPES)]
        city = IVORIAN_CITIES[index % len(IVORIAN_CITIES)]
        rows.append({
            "centre_sante_code": f"CS{index + 1:03d}",
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
        agent_row = apply_anomalies_to_row(agent_row, anomalies_config, "agent")
        
        # Ajouter à la liste
        agents.append(agent_row)
        
        # Les médecins conseils appartiennent au niveau central et ne reçoivent
        # donc volontairement aucune affectation géographique.
        if agent_type == "accueil":
            assignments.append({
                "centre_sante_code": f"CS{index % 30 + 1:03d}",
                "agent_code": agent_code,
                "date_debut": VALID_FROM,
                "date_fin": None,
                **audit_values(),
            })
    return agents, assignments

def build_insured_people() -> list[dict[str, Any]]:
    """Crée deux mille assurés aux identifiants stables et non séquentiels."""

    rows = []
    for index in range(100000):
        last_name, first_name = synthetic_identity(index + 100)
        insured_row = {
            "personne_uuid": uuid5(NAMESPACE_URL, f"cmu-demo-assure-{index + 1}"),
            "numero_recepisse": f"REC-{2026}-{index + 1:06d}",
            "assure_numero_identifiant": f"CMU{index + 1:010d}",
            "numero_secu": f"{index + 1:013d}",
            "civilite_code": "MME" if index % 2 == 0 else "M",
            "assure_nom": last_name,
            "assure_nom_patronymique": last_name if index % 5 else f"{last_name}-{first_name}",
            **audit_values(),
        }
        
        # Appliquer les anomalies
        insured_row = apply_anomalies_to_row(insured_row, anomalies_config, "insured")
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
            "centre_sante_code": f"CS{index % 30 + 1:03d}",
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


async def seed_database() -> None:
    """Peuple toutes les tables référentielles dans une transaction unique."""

    logger.info("Démarrage du peuplement référentiel CMU.")
    agents, agent_assignments = build_agents()
    professionals, professional_specialties, professional_centers = build_professionals()
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
    logger.info("Peuplement référentiel terminé avec succès.")

def main() -> None:
    """Lance le seed et présente une erreur française en cas d'échec."""

    try:
        asyncio.run(seed_database())
    except Exception:
        logger.exception("Le peuplement référentiel a échoué ; la transaction est annulée.")
        raise
