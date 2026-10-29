# Modèle de données

Base : **PostgreSQL 16**, accès asynchrone via SQLAlchemy 2 (`asyncpg`). Le schéma est créé par une migration socle unique (`alembic/versions/20261028_0001_socle_schema_mirka.py`) ; les anciennes migrations sont archivées dans `alembic/versions_archive/` (voir son `LISEZ_MOI.md`).

## Deux familles de tables

### 1. Le schéma Mirka — `TB_SIM_*` (≈ 40 tables)

Schéma de référence de la CMU. Modèles ORM : `src/echo/web/app/models/mirka.py` (généré par `tools/generer_modeles_orm.py` depuis `schema_mirka/`). Les noms de colonnes sont en majuscules, les attributs Python en minuscules.

| Domaine | Tables |
|---|---|
| **Assurés** | `TB_SIM_ASSURES`, `_ASSURES_DROITS`, `_ASSURES_IDENTIFIANTS`, `_ASSURES_INFOS_NAISSANCE`, `_ASSURES_PROFESSIONS` |
| **Collectivités** | `TB_SIM_REF_COLLECTIVITES`, `_REF_COLLECTIVITES_ADRESSES` |
| **Centres et professionnels** | `TB_SIM_REF_CENTRES_SANTE`, `_AGENTS`, `_CENTRES_SANTE_AGENTS`, `_REF_PROFESSIONNELS_SANTE`, `_REF_PROFESSIONNELS_SANTE_SPECIALITES_MEDICALES`, `_CENTRES_SANTE_PROFESSIONNELS_SANTE`, `_TV_SPECIALITES_MEDICALES` |
| **Référentiels de soins** | `TB_SIM_REF_PATHOLOGIES`, `_REF_MEDICAMENTS`, `_REF_MEDICAMENTS_DCI`, `_REF_ACTES_MEDICAUX` |
| **Factures** | `TB_SIM_FACTURES`, `_FACTURES_PATHOLOGIES`, `_FACTURES_PRESCRIPTIONS`, `_FACTURES_PRESTATIONS`, `_FACTURES_REJETS`, `_FACTURES_STATUTS`, `_FACTURES_PROFESSIONNELS_SANTE`, `_TV_TYPES_FACTURES` |
| **Ententes préalables** | `TB_SIM_ENTENTES_PREALABLES`, `_ENTENTES_PREALABLES_STATUTS`, `_ENTENTES_PREALABLES_ACTES_MEDICAUX`, `_ENTENTES_PREALABLES_PRESTATIONS` |
| **Droits et produits** | `TB_SIM_DROITS`, `_PRODUITS`, `_PRODUITS_REGIMES`, `_PANIERS_SOINS`, `_RESEAUX_SOINS`, `_RESEAUX_SOINS_ACTES_MEDICAUX`, `_TV_REGIMES` |
| **Localisation** | `TB_SIM_TV_LOCALISATION_PAYS`, `_REGIONS`, `_DEPARTEMENTS`, `_LOCALITES` |

Le préfixe `TV_` désigne une table de valeurs (liste fermée). Les clés des assurés et des utilisateurs sont des UUID.

### 2. Les tables propres à ÉCHO — `TB_*`

| Table | Rôle | Module |
|---|---|---|
| `TB_UTILISATEURS` | Comptes : email, nom d'utilisateur, hash bcrypt, rôle, statut actif, mot de passe temporaire à changer, dernière connexion | `web/auth/models.py` |
| `TB_SIMULATIONS` | Une ligne par exécution du moteur (profil, réglages, bornes, bilan) | `moteur/simulation/models.py` |
| `TB_REFUS_ACCUEIL` | Registre des passages refusés à l'accueil (droits fermés, etc.) | `moteur/simulation/models.py` |
| `TB_EVENEMENTS_METIER` | Journal des événements du bus | `moteur/events/models.py` |
| `TB_CONFIG_ANOMALIES` | Configuration d'injection et compteur d'anomalies | `metier/anomalies/models.py` |
| `TB_REF_ANOMALIES` | Catalogue des types d'anomalies (la base fait foi après le premier peuplement) | `metier/anomalies/models.py` |
| `TB_ANOMALIES_INJECTIONS` | Journal de chaque injection | `metier/anomalies/models.py` |
| `TB_CAMPAGNES` | Campagnes de test (référence, palier, volume, graine, statut) | `metier/campagnes/models.py` |
| `TB_CAMPAGNES_CORRIGE` | Corrigé : les anomalies exactement posées dans le jeu | `metier/campagnes/models.py` |
| `TB_CAMPAGNES_ECHANGES` | Historique des transmissions à l'outil testé | `metier/campagnes/models.py` |
| `TB_MDM_PAIRES` | Paires d'identités et vérité terrain du rapprochement | `metier/mdm/models.py` |

## Schéma de référence et génération de code

`schema_mirka/` contient les sources : `ossature.sql` (DDL), `schema_sim.json`, et les classeurs `COLONNES.xlsx`, `CONTRAINTE.xlsx`, `index.xlsx`. Les scripts de `tools/` en dérivent le code :

| Script | Produit |
|---|---|
| `extraire_schema_mirka.py` | Extrait le schéma depuis les sources |
| `generer_modeles_orm.py` | `web/app/models/mirka.py` |
| `generer_tables_sim.py` | `moteur/simulation/schema_sim/tables_generees.py` |
| `verifier_attributs_modeles.py` | Contrôle la cohérence des modèles |
| `verifier_seeds.py` | Contrôle les données de départ |

Ne pas éditer à la main les fichiers générés : modifier la source et relancer le script.

## Données de référence (seed)

`python -m echo.moteur.seed` alimente les référentiels à partir de fichiers CSV réels sous `src/echo/moteur/seed/donnees/` : établissements CNAM, pharmacies, médicaments CMU, coordonnées des localités. La couverture de départ est réglée par `TAUX_COUVERTURE` (0,60 par défaut). `python -m echo.moteur.seed.reinitialiser` repart de zéro. Les identifiants (numéros d'immatriculation) sont produits par `identifiants.py` ; la provenance de chaque jeu est documentée par `provenance.py` et exposée via `/gouvernance/provenance`.

Voir aussi [guides/referentiels_cnam_et_identifiants.md](guides/referentiels_cnam_et_identifiants.md).

## Migrations

```powershell
$env:PYTHONPATH = "src"
python -m alembic upgrade head                       # appliquer
python -m alembic revision -m "description"          # créer
python -m alembic downgrade -1                       # annuler la dernière
```

Sauvegarder avant toute migration en production (script `deploiement/sauvegarde.sh`, voir [GUIDE_EXPLOITATION.md](GUIDE_EXPLOITATION.md)).
