from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from datetime import date, datetime, timedelta, timezone
import unicodedata
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from faker import Faker
from sqlalchemy import func, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_factory
from app.models import (
    Agent, CenterHealthAgent, Collectivite, Country, Dci, Department,
    HealthCenter, HealthProfessional, HealthProfessionalCenter,
    HealthProfessionalMedicalSpecialty, InsuredBirthInfo, InsuredIdentifier,
    InsuredPerson, InsuredProfession, InsuredRight, Locality, MedicalAct,
    MedicalSpecialty, Medication, Pathology, Pharmacie, Regime, Region,
    TypeInvoice,
)

from seed.constants import (
    COUNTRIES, HEALTH_CENTER_TYPES, INVOICE_TYPES, IVORIAN_CITIES,
    IVORIAN_DISTRICTS, IVORIAN_FIRST_NAMES, IVORIAN_LAST_NAMES, MEDECINS_CONSEILS,
    MEDICAL_ACTS, MEDICAL_SPECIALTIES, PATHOLOGY_LABELS, PROFESSIONS,
)
from seed.donnees import ETABLISSEMENTS, MEDICAMENTS, PHARMACIES, lire as lire_donnees
from seed.identifiants import brouiller, numero, numero_securite_sociale
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
NOMBRE_ASSURES = 100_000

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


# ── Offre de soins : la liste publique de la CNAM ────────────────────────
#
# Établissements, pharmacies et localités viennent de seed/donnees (liste
# ipscnam.ci). Les noms sont officiels ; les codes, eux, sont propres au
# simulateur et suivent la règle commune : que des chiffres, jamais
# consécutifs (seed/identifiants.py). Le rang d'une ligne dans le fichier
# fixe son numéro : le fichier est trié, le seed reste reproductible.

def build_collectivites(etablissements: list[dict[str, str]],
                        pharmacies: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Une ligne par localité citée, qu'elle ait un établissement ou une pharmacie."""

    noms = sorted({ligne["localite"] for ligne in etablissements}
                  | {ligne["localite"] for ligne in pharmacies})
    return [
        {"collectivite_code": numero("collectivite", rang),
         "collectivite_denomination": nom, **audit_values()}
        for rang, nom in enumerate(noms)
    ]


def build_health_centers(etablissements: list[dict[str, str]],
                         codes_collectivite: dict[str, str]) -> list[dict[str, Any]]:
    """Les 1 510 établissements de la liste CNAM, avec leur localité réelle."""

    types_connus = {code for code, _ in HEALTH_CENTER_TYPES}
    rows = []
    for rang, ligne in enumerate(etablissements):
        if ligne["type_code"] not in types_connus:
            raise ValueError(f"Type d'établissement inconnu : {ligne['type_code']}.")
        rows.append({
            "centre_sante_code": numero("centre", rang),
            "collectivite_code": codes_collectivite[ligne["localite"]],
            "type_etablissement_sanitaire_code": ligne["type_code"],
            "centre_sante_numero_immatriculation": numero("immatriculation_centre", rang),
            "centre_sante_denomination": ligne["denomination"],
            **audit_values(),
        })
    return rows


def build_pharmacies(pharmacies: list[dict[str, str]],
                     codes_collectivite: dict[str, str]) -> list[dict[str, Any]]:
    """Les pharmacies de la liste CNAM où un assuré CMU retire ses médicaments."""

    return [
        {"pharmacie_code": numero("pharmacie", rang),
         "pharmacie_denomination": ligne["denomination"],
         "collectivite_code": codes_collectivite[ligne["localite"]],
         **audit_values()}
        for rang, ligne in enumerate(pharmacies)
    ]


def synthetic_identity(index: int) -> tuple[str, str]:
    """Mélange de façon déterministe noms ivoiriens et prénoms Faker."""

    last_name = IVORIAN_LAST_NAMES[index % len(IVORIAN_LAST_NAMES)]
    first_name = (
        IVORIAN_FIRST_NAMES[index % len(IVORIAN_FIRST_NAMES)]
        if index % 3 != 0 else fake.first_name()
    )
    return last_name, first_name


def _agent(rang_gestion: int, identite: int, code: str, type_agent: str) -> dict[str, Any]:
    """Une fiche agent, anomalies du seed appliquées."""

    last_name, first_name = synthetic_identity(identite)
    email_root = (normalize_text(f"{first_name}.{last_name}").lower()
                  .replace("'", "").replace(" ", ""))
    row = {
        "agent_code": code,
        "agent_code_gestion": numero("agent_gestion", rang_gestion),
        "agent_prenoms": first_name,
        "agent_nom": last_name,
        "agent_email": f"{email_root}.{code}@cmu.demo.ci",
        "agent_type_code": type_agent,
        **audit_values(),
    }
    return apply_anomalies_to_row(row, anomalies_seed, "agent")


def build_agents(centres: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Un agent d'accueil par centre, et vingt médecins conseils centraux.

    Les deux populations restent dans TB_REF_AGENTS mais n'ont pas la même
    longueur de code — cinq chiffres pour l'accueil, quatre pour les médecins
    conseils : un numéro ne peut jamais désigner l'un et l'autre, et sa
    longueur suffit à dire lequel.
    """

    agents, assignments = [], []
    for rang, centre in enumerate(centres):
        code = numero("agent_accueil", rang)
        agents.append(_agent(rang, rang, code, "accueil"))
        assignments.append({
            "centre_sante_code": centre["centre_sante_code"],
            "agent_code": code,
            "date_debut": VALID_FROM,
            "date_fin": None,
            **audit_values(),
        })

    # Les médecins conseils appartiennent au niveau central et ne reçoivent
    # donc volontairement aucune affectation géographique.
    for rang in range(MEDECINS_CONSEILS):
        code = numero("medecin_conseil", rang)
        agents.append(_agent(len(centres) + rang, 5_000 + rang, code, "medecin_conseil"))
    return agents, assignments


def build_professionals(centres: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Deux professionnels par centre : un médecin et un infirmier."""

    professionals, specialties, centers = [], [], []
    for rang_centre, centre in enumerate(centres):
        for position, type_code in enumerate(("medecin", "infirmier")):
            rang = rang_centre * 2 + position
            last_name, first_name = synthetic_identity(rang + 300)
            code = numero("professionnel", rang)
            professionals.append({
                "professionnel_sante_code": code,
                "nom": last_name,
                "prenoms": first_name,
                "type_code": type_code,
                # Un seul espace de rangs pour les deux ordres : un médecin et
                # un infirmier ne peuvent pas porter le même numéro.
                "numero_ordre": numero("numero_ordre", rang),
                "statut": "actif",
                **audit_values(),
            })
            centers.append({
                "professionnel_sante_code": code,
                "centre_sante_code": centre["centre_sante_code"],
                "date_debut": VALID_FROM,
                "date_fin": None,
                **audit_values(),
            })
            if type_code == "medecin":
                specialties.append({
                    "professionnel_sante_code": code,
                    "specialite_medicale_code": MEDICAL_SPECIALTIES[rang_centre % len(MEDICAL_SPECIALTIES)][0],
                    "date_debut": VALID_FROM,
                    "date_fin": None,
                    **audit_values(),
                })
    return professionals, specialties, centers


# ── Assurés ──────────────────────────────────────────────────────────────

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
    for index in range(NOMBRE_ASSURES):
        last_name, first_name = synthetic_identity(index + 100)
        date_naissance, regime = insured_profile(index)
        insured_row = {
            "personne_uuid": uuid5(NAMESPACE_URL, f"cmu-demo-assure-{index + 1}"),
            "numero_recepisse": numero("recepisse", index),
            "assure_numero_identifiant": numero("assure_identifiant", index),
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


# ── Nomenclatures ────────────────────────────────────────────────────────

def build_pathologies() -> list[dict[str, Any]]:
    """Transforme les cent libellés en codes numériques de trois chiffres."""

    return [
        {
            "pathologie_code": numero("pathologie", index),
            "pathologie_date_debut": VALID_FROM,
            "sous_chapitre_code": numero("sous_chapitre", index // 10),
            "pathologie_denomination": label,
            "pathologie_date_fin": None,
            "pathologie_statut": "actif",
            **audit_values(),
        }
        for index, label in enumerate(PATHOLOGY_LABELS)
    ]


# Forme pharmaceutique lue dans le libellé, de la plus distinctive à la plus
# courante : « SOL INJECTABLE » doit tomber en injectable, pas en solution
# buvable. Codes mnémoniques, comme les types d'établissement.
FORMES_MEDICAMENT = (
    ("INJ", r"INJ|\bAMP\b|AMPOULE|PERF|\bI\.?V\b|S/C|SERINGUE|STYLO|CARTOUCHE|FLACON DE \d+ ?ML"),
    ("COL", r"COLLYRE|\bCOLL\b|OPHT"),
    ("BUV", r"SIROP|\bSIR\b|SUSP|BUV|GOUTTES|\bGTT\b|\bPDR\b|POUDRE|SACHET|\bSAC\b"),
    ("TOP", r"POMMADE|\bPOM\b|CREME|\bCR\b|\bGEL\b|LOTION|DERM|SPRAY|POUDRE CUT"),
    ("SUP", r"SUPPO|OVULE|\bOV\b|VAG"),
    ("CPR", r"CPR|COMPRIM|GELULE|\bGLE|CAPS|\bCP\b|DRAG|\bCOMP\b"),
)
FORME_PAR_DEFAUT = "DIV"

# Tarif indicatif (FCFA) des spécialités dont la CNAM ne publie pas le prix.
# Hypothèse consignée dans seed/provenance.py.
TARIFS_INDICATIFS = {"CPR": 2500, "BUV": 2000, "INJ": 3500, "COL": 2500,
                     "TOP": 1800, "SUP": 2000, FORME_PAR_DEFAUT: 2000}


def forme_medicament(libelle: str) -> str:
    return next((code for code, motif in FORMES_MEDICAMENT
                 if re.search(motif, libelle.upper())), FORME_PAR_DEFAUT)


def tarif_medicament(rang: int, prix_publie: str, forme: str) -> Decimal:
    """Le prix CNAM quand il est publié ; sinon un tarif indicatif selon la
    forme, décalé de ±30 % de façon stable pour ne pas aligner 741 prix
    identiques."""

    if prix_publie:
        return Decimal(prix_publie)
    variation = random.Random(RANDOM_SEED + 50_000 + rang).uniform(0.7, 1.3)
    return (Decimal(TARIFS_INDICATIFS[forme]) * Decimal(str(round(variation, 2)))).quantize(Decimal("1"))


def build_dci(medicaments: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Une ligne par dénomination commune de la liste CMU."""

    return [
        {"dci_code": numero("dci", rang), "dci_denomination": nom, **audit_values()}
        for rang, nom in enumerate(sorted({ligne["dci"] for ligne in medicaments}))
    ]


def build_medications(medicaments: list[dict[str, str]],
                      codes_dci: dict[str, str]) -> list[dict[str, Any]]:
    """Les 918 spécialités de la liste CMU publiée par la CNAM.

    Le laboratoire, le conditionnement et la présentation ne sont pas publiés :
    ils restent vides plutôt que d'être inventés.
    """

    rows = []
    for rang, ligne in enumerate(medicaments):
        forme = forme_medicament(ligne["libelle"])
        rows.append({
            "medicament_code": numero("medicament", rang),
            "medicament_date_debut": VALID_FROM,
            "type_code": None,
            "medicament_denomination": ligne["libelle"],
            # 618 est le préfixe GS1 de la Côte d'Ivoire ; les neuf chiffres
            # d'article suivent la règle commune, le dernier est la clé EAN.
            "medicament_ean13": calculate_ean13("618" + numero("ean13_article", rang)),
            "dci_code": codes_dci[ligne["dci"]],
            "laboratoire_code": None,
            "famille_forme_code": forme,
            "conditionnement_code": None,
            "presentation_code": None,
            "liste_types_factures": "PHA",
            "liste_genres": "M,F",
            "medicament_quantite_maximum": 3,
            "medicament_age_minimum": 0,
            "medicament_age_maximum": 120,
            "medicament_hapax_statut": False,
            "medicament_tarif_default": tarif_medicament(rang, ligne["prix_fcfa"], forme),
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
            "article_code": numero("article_acte", index),
            "acte_medical_type": act_type,
            "acte_medical_denomination": label,
            "acte_medical_tarif": Decimal(tariff),
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
    hiérarchie lisible sans jointure : six chiffres pour la région, un de
    plus pour le département, un de plus pour la localité (412893 ->
    4128937 -> 41289372). Aucun niveau n'est numéroté dans l'ordre.
    """

    regions, departments, localities = [], [], []

    for district_index, (nom, latitude, longitude) in enumerate(IVORIAN_DISTRICTS):
        region_code = numero("region", district_index)
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
            department_code = region_code + brouiller(
                department_index, 1, f"departement:{region_code}")
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
                    "localite_code": department_code + brouiller(
                        locality_index, 1, f"localite:{department_code}"),
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
        # Trois assurés sur dix présentent en plus une pièce d'identité. Le
        # type est porté par sa colonne : le numéro, lui, n'a plus de préfixe.
        if generator.random() < 0.30:
            type_code = generator.choice(["CNI", "PASSPT", "ATTEST"])
            rows.append({
                "personne_uuid": assure["personne_uuid"],
                "type_identifiant_code": type_code,
                "identifiant_date_debut": VALID_FROM_TS,
                "identifiant_numero": numero("piece_identite", index),
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
                # Un rang par (assuré, mois) : douze numéros distincts par
                # assuré, aucun ne suit le précédent.
                "droits_id": numero("droits", index * 12 + mois - 1),
                "droits_statut": 0 if mois in mois_fermes else 1,
                "droits_date_debut": debut,
                "droits_date_fin": fin - timedelta(seconds=1),
                **audit_values(),
            })
    return rows

async def seed_database() -> None:
    """Peuple toutes les tables référentielles dans une transaction unique."""

    logger.info("Démarrage du peuplement référentiel CMU.")
    etablissements = lire_donnees(ETABLISSEMENTS)
    officines = lire_donnees(PHARMACIES)
    liste_cmu = lire_donnees(MEDICAMENTS)

    collectivites = build_collectivites(etablissements, officines)
    codes_collectivite = {ligne["collectivite_denomination"]: ligne["collectivite_code"]
                          for ligne in collectivites}
    centres = build_health_centers(etablissements, codes_collectivite)
    dci = build_dci(liste_cmu)
    codes_dci = {ligne["dci_denomination"]: ligne["dci_code"] for ligne in dci}

    agents, agent_assignments = build_agents(centres)
    professionals, professional_specialties, professional_centers = build_professionals(centres)
    regions, departments, localities = build_localisation()
    datasets = {
        "assures": build_insured_people(), "centres": centres,
        "pharmacies": build_pharmacies(officines, codes_collectivite),
        "agents": agents, "affectations_agents": agent_assignments,
        "professionnels": professionals, "specialites_professionnels": professional_specialties,
        "centres_professionnels": professional_centers, "pathologies": build_pathologies(),
        "medicaments": build_medications(liste_cmu, codes_dci), "actes": build_medical_acts(),
    }
    # Les volumes suivent la liste CNAM : un agent d'accueil et deux
    # professionnels par établissement, vingt médecins conseils au-dessus.
    expected = {
        "assures": NOMBRE_ASSURES, "centres": len(etablissements),
        "pharmacies": len(officines),
        "agents": len(etablissements) + MEDECINS_CONSEILS,
        "affectations_agents": len(etablissements),
        "professionnels": 2 * len(etablissements),
        "specialites_professionnels": len(etablissements),
        "centres_professionnels": 2 * len(etablissements),
        "pathologies": len(PATHOLOGY_LABELS), "medicaments": len(liste_cmu),
        "actes": len(MEDICAL_ACTS),
    }
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
            await upsert_rows(session, Collectivite, collectivites)
            await upsert_rows(session, HealthCenter, datasets["centres"])
            await upsert_rows(session, Pharmacie, datasets["pharmacies"])
            await upsert_rows(session, Agent, datasets["agents"])
            await upsert_rows(session, MedicalSpecialty, specialties)
            await upsert_rows(session, HealthProfessional, datasets["professionnels"])
            await upsert_rows(session, Pathology, datasets["pathologies"])
            await upsert_rows(session, Dci, dci)
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
