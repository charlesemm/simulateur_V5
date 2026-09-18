"""Référentiels chargés depuis la liste publique de la CNAM.

Aucun accès à la base : on vérifie ce que le seed s'apprête à écrire —
volumes, formats des codes, et ce qui relie les tables entre elles.
"""
from __future__ import annotations

import re
from decimal import Decimal

from seed.constants import HEALTH_CENTER_TYPES
from seed.donnees import ETABLISSEMENTS, MEDICAMENTS, PHARMACIES, lire
from seed.runner import (
    MEDECINS_CONSEILS, build_agents, build_collectivites, build_dci,
    build_health_centers, build_localisation, build_medications,
    build_pharmacies, build_professionals, calculate_ean13,
)

LISTE_ETABLISSEMENTS = lire(ETABLISSEMENTS)
LISTE_PHARMACIES = lire(PHARMACIES)
LISTE_CMU = lire(MEDICAMENTS)


def _entier(chiffres: int) -> re.Pattern[str]:
    """Un entier de N chiffres, sans zéro de tête."""

    return re.compile(rf"[1-9]\d{{{chiffres - 1}}}")


def _centres() -> tuple[list[dict], dict[str, str]]:
    collectivites = build_collectivites(LISTE_ETABLISSEMENTS, LISTE_PHARMACIES)
    codes = {ligne["collectivite_denomination"]: ligne["collectivite_code"]
             for ligne in collectivites}
    return build_health_centers(LISTE_ETABLISSEMENTS, codes), codes


def test_la_liste_cnam_compte_1510_etablissements_de_types_connus():
    assert len(LISTE_ETABLISSEMENTS) == 1510
    connus = {code for code, _ in HEALTH_CENTER_TYPES}
    assert {ligne["type_code"] for ligne in LISTE_ETABLISSEMENTS} <= connus


def test_codes_et_immatriculations_de_centre_sont_des_entiers_uniques():
    centres, _ = _centres()
    codes = [centre["centre_sante_code"] for centre in centres]
    immatriculations = [centre["centre_sante_numero_immatriculation"] for centre in centres]

    assert all(_entier(7).fullmatch(code) for code in codes)
    assert all(_entier(8).fullmatch(valeur) for valeur in immatriculations)
    assert len(set(codes)) == len(codes)
    assert len(set(immatriculations)) == len(immatriculations)


def test_chaque_centre_et_chaque_pharmacie_ont_une_localite_connue():
    centres, codes = _centres()
    pharmacies = build_pharmacies(LISTE_PHARMACIES, codes)

    assert {centre["collectivite_code"] for centre in centres} <= set(codes.values())
    assert {officine["collectivite_code"] for officine in pharmacies} <= set(codes.values())
    assert len(pharmacies) == len(LISTE_PHARMACIES)
    assert all(_entier(6).fullmatch(officine["pharmacie_code"]) for officine in pharmacies)


def test_medecins_conseils_et_agents_d_accueil_ne_partagent_aucun_numero():
    """Quatre chiffres pour l'un, cinq pour l'autre : la longueur dit qui est qui."""

    centres, _ = _centres()
    agents, affectations = build_agents(centres)
    conseils = [agent["agent_code"] for agent in agents
                if agent["agent_type_code"] == "medecin_conseil"]
    accueil = [agent["agent_code"] for agent in agents
               if agent["agent_type_code"] == "accueil"]

    assert len(conseils) == MEDECINS_CONSEILS == 20
    assert all(_entier(4).fullmatch(code) for code in conseils)
    assert len(accueil) == len(centres) == len(affectations)
    assert all(_entier(5).fullmatch(code) for code in accueil)
    assert len(set(conseils) | set(accueil)) == len(agents)


def test_deux_professionnels_par_centre_aux_numeros_uniques():
    centres, _ = _centres()
    professionnels, specialites, affectations = build_professionals(centres)
    codes = [pro["professionnel_sante_code"] for pro in professionnels]
    ordres = [pro["numero_ordre"] for pro in professionnels]

    assert len(professionnels) == len(affectations) == 2 * len(centres)
    assert len(specialites) == len(centres)
    assert len(set(codes)) == len(codes) and len(set(ordres)) == len(ordres)


def test_les_918_medicaments_gardent_le_prix_publie_quand_il_existe():
    dci = build_dci(LISTE_CMU)
    codes_dci = {ligne["dci_denomination"]: ligne["dci_code"] for ligne in dci}
    medicaments = build_medications(LISTE_CMU, codes_dci)

    assert len(medicaments) == len(LISTE_CMU) == 918
    assert len({ligne["medicament_code"] for ligne in medicaments}) == 918
    for source, medicament in zip(LISTE_CMU, medicaments):
        assert medicament["medicament_tarif_default"] > 0
        if source["prix_fcfa"]:
            assert medicament["medicament_tarif_default"] == Decimal(source["prix_fcfa"])
        ean = medicament["medicament_ean13"]
        assert len(ean) == 13 and ean.startswith("618")
        assert calculate_ean13(ean[:12]) == ean


def test_les_collectivites_geocodees_restent_en_cote_d_ivoire():
    """Coordonnées optionnelles (localité non trouvée) mais jamais hors du pays."""

    collectivites = build_collectivites(LISTE_ETABLISSEMENTS, LISTE_PHARMACIES)
    avec_coordonnees = [c for c in collectivites if c["collectivite_latitude"] is not None]

    assert avec_coordonnees, "aucune localité géocodée : localites_coordonnees.csv est-il à jour ?"
    for collectivite in avec_coordonnees:
        latitude = Decimal(collectivite["collectivite_latitude"])
        longitude = Decimal(collectivite["collectivite_longitude"])
        assert Decimal("4") <= latitude <= Decimal("11")
        assert Decimal("-9") <= longitude <= Decimal("-2")


def test_la_hierarchie_de_localisation_reste_lisible_par_prefixe():
    regions, departements, localites = build_localisation()

    assert all(_entier(6).fullmatch(region["region_code"]) for region in regions)
    for departement in departements:
        assert len(departement["departement_code"]) == 7
        assert departement["departement_code"][:6] == departement["region_code"]
    for localite in localites:
        assert len(localite["localite_code"]) == 8
        assert localite["localite_code"][:7] == localite["departement_code"]
    assert len({localite["localite_code"] for localite in localites}) == len(localites)
