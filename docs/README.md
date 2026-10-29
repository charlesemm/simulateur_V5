# Documentation d'ÉCHO — Simulateur de données CMU

ÉCHO est le simulateur de données de la CMU (CNAM Côte d'Ivoire). Il joue le parcours de soins d'un assuré (accueil, facture, prestations, médicaments, ententes préalables), y injecte des anomalies et des pannes à la demande, et sert à éprouver des outils de qualité des données. Un tableau de bord React le pilote et l'observe en direct.

## Par où commencer

| Je veux… | Je lis |
|---|---|
| Lancer l'application en local | [README du dépôt](../README.md) |
| Comprendre comment c'est construit | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Appeler l'API | [REFERENCE_API.md](REFERENCE_API.md) |
| Comprendre la base de données | [MODELE_DONNEES.md](MODELE_DONNEES.md) |
| Savoir ce que le moteur simule, les anomalies et les aléas | [MOTEUR_ET_ANOMALIES.md](MOTEUR_ET_ANOMALIES.md) |
| Utiliser les campagnes de test qualité | [CAMPAGNES_QUALITE.md](CAMPAGNES_QUALITE.md) |
| Utiliser ou modifier le dashboard | [DASHBOARD.md](DASHBOARD.md) |
| Régler l'application, les rôles, la sécurité | [CONFIGURATION_ET_SECURITE.md](CONFIGURATION_ET_SECURITE.md) |
| Développer, tester, migrer | [DEVELOPPEMENT.md](DEVELOPPEMENT.md) |
| Conteneuriser, déployer, exploiter | [GUIDE_PODMAN.md](GUIDE_PODMAN.md), [GUIDE_CICD.md](GUIDE_CICD.md), [GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md), [GUIDE_EXPLOITATION.md](GUIDE_EXPLOITATION.md) |

## Les guides par module (module Qualité des données)

Ils racontent la construction du module campagnes, un module à la fois :
[M1 campagne](guides/M1_campagne.md) · [M2 choix des anomalies](guides/M2_choix_des_anomalies.md) · [M3 générateur et corrigé](guides/M3_generateur_et_corrige.md) · [M4 export marqué](guides/M4_export_marque.md) · [M5 anomalies manquantes](guides/M5_anomalies_manquantes.md) · [M6 canal API](guides/M6_canal_api.md) · [alignement données libre / qualité](guides/alignement_donnees_libre_qualite.md) · [référentiels CNAM et identifiants](guides/referentiels_cnam_et_identifiants.md).

Le cahier des charges d'origine est dans [cahier_des_charges/](cahier_des_charges/).

## Vocabulaire

| Terme | Sens |
|---|---|
| **Passage** | Un parcours de soins complet joué par le moteur pour un assuré, de l'accueil à la clôture de la facture |
| **Exécution** | Une session de simulation (`TB_SIMULATIONS`), du démarrage à l'arrêt |
| **Profil / type de simulation** | `LIBRE`, `QUALITE`, `MDM`, `ENTREPOT`, `GOUVERNANCE` : un réglage de départ |
| **Anomalie** | Une valeur faussée volontairement (montant aberrant, doublon…) |
| **Aléa** | Une panne ou perturbation du déroulement (coupure, base lente…) |
| **Campagne** | Un jeu de données piégé, généré avec une graine, pour tester un outil externe |
| **Corrigé** | La liste exacte des anomalies d'une campagne, gardée par ÉCHO pour noter l'outil testé |
| **Témoin** | Un outil de qualité de référence intégré, qui reçoit et analyse un jeu |
| **Graine** | Entier qui rend un tirage aléatoire rejouable à l'identique |
| **Mirka** | Nom du schéma de référence des tables `TB_SIM_*` |
