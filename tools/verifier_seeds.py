"""Confronte les lignes produites par les seeds aux modèles, sans base.

Semer cent mille assurés pour découvrir qu'une colonne obligatoire manque est
une façon coûteuse d'apprendre. Ce script construit un échantillon de chaque
jeu, puis vérifie deux choses que seule la base dirait autrement :

- qu'aucune clé ne désigne un attribut absent du modèle,
- qu'aucune colonne obligatoire ne reste vide alors que ni la base ni le
  modèle ne lui donnent de valeur par défaut.

Il ne remplace pas un semis réel : il ne voit ni les clés étrangères ni les
longueurs dépassées. Il attrape ce qui casse le plus souvent après un
changement de schéma.
"""

from __future__ import annotations

import sys
from typing import Any, Callable

from sqlalchemy.orm import configure_mappers

import echo.web.app.models as modeles
from echo.moteur.seed import runner

ECHANTILLON = 3


def _jeux() -> list[tuple[str, type, Callable[[], list[dict[str, Any]]]]]:
    """Chaque jeu de seed, avec le modèle qu'il alimente.

    Les jeux qui dépendent d'autres sont construits à la demande, pour que ce
    script reste lisible sans rejouer l'ordonnancement de `seed_database`.
    """
    # Les vraies listes CNAM : des fixtures inventées ne vérifieraient que
    # mes propres suppositions sur leur forme.
    etablissements = runner.lire_donnees(runner.ETABLISSEMENTS)
    officines = runner.lire_donnees(runner.PHARMACIES)
    liste_cmu = runner.lire_donnees(runner.MEDICAMENTS)
    collectivites = runner.build_collectivites(etablissements, officines)
    codes_collectivite = {l["collectivite_denomination"]: l["collectivite_code"]
                          for l in collectivites}
    centres = runner.build_health_centers(etablissements, codes_collectivite)
    dci = runner.build_dci(liste_cmu)
    codes_dci = {l["dci_denomination"]: l["dci_code"] for l in dci}
    assures = runner.build_insured_people()[:50]
    regions, departements, localites = runner.build_localisation()
    agents, affectations = runner.build_agents(centres)
    professionnels, specialites, rattachements = runner.build_professionals(centres)

    return [
        ("regimes", modeles.Regime, runner.build_regimes),
        ("pays", modeles.Country, runner.build_countries),
        ("regions", modeles.Region, lambda: regions),
        ("departements", modeles.Department, lambda: departements),
        ("localites", modeles.Locality, lambda: localites),
        ("produits", modeles.Product, runner.build_products),
        ("produits_regimes", modeles.ProductRegime, runner.build_products_regimes),
        ("paniers_soins", modeles.CareBasket, runner.build_care_baskets),
        ("reseaux_soins", modeles.CareNetwork, runner.build_care_networks),
        ("tarifs_reseau", modeles.NetworkMedicalAct, runner.build_network_medical_acts),
        ("assures", modeles.InsuredPerson, lambda: assures),
        ("droits_produit", modeles.InsuredEntitlement,
         lambda: runner.build_insured_entitlements(assures)),
        ("droits_mensuels", modeles.InsuredRight,
         lambda: runner.build_insured_rights(assures)),
        ("identifiants", modeles.InsuredIdentifier,
         lambda: runner.build_insured_identifiers(assures)),
        ("professions", modeles.InsuredProfession,
         lambda: runner.build_insured_professions(assures)),
        ("naissances", modeles.InsuredBirthInfo,
         lambda: runner.build_insured_birth_infos(assures, localites)),
        ("centres", modeles.HealthCenter, lambda: centres),
        ("pharmacies", modeles.HealthCenter,
         lambda: runner.build_pharmacies(officines, codes_collectivite)),
        ("collectivites", modeles.Collectivite, lambda: collectivites),
        ("adresses_collectivites", modeles.CollectiviteAddress,
         lambda: runner.build_collectivites_adresses(collectivites)),
        ("dci", modeles.Dci, lambda: dci),
        ("medicaments", modeles.Medication,
         lambda: runner.build_medications(liste_cmu, codes_dci)),
        ("agents", modeles.Agent, lambda: agents),
        ("affectations_agents", modeles.CenterHealthAgent, lambda: affectations),
        ("specialites", modeles.MedicalSpecialty, lambda: specialites),
        ("professionnels", modeles.HealthProfessional, lambda: professionnels),
        ("rattachements", modeles.HealthProfessionalMedicalSpecialty, lambda: rattachements),
        ("pathologies", modeles.Pathology, runner.build_pathologies),
        ("actes", modeles.MedicalAct, runner.build_medical_acts),
    ]


def _obligatoires_sans_valeur(modele: type, ligne: dict[str, Any]) -> list[str]:
    """Colonnes obligatoires qu'aucune valeur ne viendra remplir."""
    manquantes = []
    for colonne in modele.__table__.columns:
        if colonne.nullable or colonne.server_default is not None or colonne.default is not None:
            continue
        attribut = next(
            (a.key for a in modele.__mapper__.column_attrs if a.expression is colonne), None
        )
        if attribut and ligne.get(attribut) is None:
            manquantes.append(colonne.name)
    return manquantes


def main() -> int:
    configure_mappers()
    problemes: list[str] = []

    for nom, modele, construire in _jeux():
        try:
            lignes = construire()
        except Exception as erreur:  # noqa: BLE001 - on veut tout rapporter
            problemes.append(f"{nom} : construction impossible — {erreur}")
            continue
        if not lignes:
            problemes.append(f"{nom} : aucun jeu produit")
            continue

        attendus = {a.key for a in modele.__mapper__.column_attrs}
        for ligne in lignes[:ECHANTILLON]:
            for inconnue in sorted(set(ligne) - attendus):
                problemes.append(f"{nom} -> {modele.__name__} : clé inconnue « {inconnue} »")
            for vide in _obligatoires_sans_valeur(modele, ligne):
                problemes.append(f"{nom} -> {modele.__name__} : {vide} obligatoire et vide")
            # Construire l'instance confronte les valeurs au mapper lui-même.
            # On capture plutôt que de laisser remonter : un rapport complet
            # vaut mieux qu'un arrêt sur la première rupture.
            try:
                modele(**ligne)
            except TypeError as erreur:
                problemes.append(f"{nom} -> {modele.__name__} : {erreur}")

        print(f"  {len(lignes):7d}  {nom:22s} -> {modele.__tablename__}")

    print()
    if problemes:
        print(f"{len(problemes)} problemes :")
        for probleme in sorted(set(problemes)):
            print("  ", probleme)
        return 1
    print("Tous les jeux de seed correspondent aux modeles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
