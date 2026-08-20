# GUIDE 0 — Remise en route sur une nouvelle machine

> **Objectif** : rendre le projet `simulateur_V5` totalement fonctionnel en local
> (API + base de données + dashboard), sans Docker, sur une machine vierge.
>
> **Mode de travail** : ce guide décrit chaque action, ce à quoi elle sert, et les
> fichiers du projet qu'elle met en jeu. Aucune commande n'est exécutée à ta place.
>
> **Date de rédaction** : 20 août 2026
> **Chantier** : 0 / 7 — voir la feuille de route en fin de document.

---

## Table des matières

1. [État des lieux de la machine](#1--état-des-lieux-de-la-machine)
2. [Comprendre ce qu'on va faire et pourquoi](#2--comprendre-ce-quon-va-faire-et-pourquoi)
3. [Le problème du fichier `.env`](#3--le-problème-du-fichier-env)
4. [Vue d'ensemble des étapes](#4--vue-densemble-des-étapes)
5. [Étape 1 — Rendre `psql` accessible](#étape-1--rendre-psql-accessible)
6. [Étape 2 — Créer la base de données](#étape-2--créer-la-base-de-données)
7. [Étape 3 — Activer le venv et définir la connexion](#étape-3--activer-le-venv-et-définir-la-connexion)
8. [Étape 4 — Construire le schéma (Alembic)](#étape-4--construire-le-schéma-alembic)
9. [Étape 5 — Créer le compte administrateur](#étape-5--créer-le-compte-administrateur)
10. [Étape 6 — Charger les données référentielles (seed)](#étape-6--charger-les-données-référentielles-seed)
11. [Étape 7 — Démarrer l'API](#étape-7--démarrer-lapi)
12. [Étape 8 — Installer et démarrer le dashboard](#étape-8--installer-et-démarrer-le-dashboard)
13. [Étape 9 — Se connecter et vérifier](#étape-9--se-connecter-et-vérifier)
14. [Rituel de démarrage quotidien](#rituel-de-démarrage-quotidien)
15. [Annexe A — Les 24 tables du schéma](#annexe-a--les-24-tables-du-schéma)
16. [Annexe B — Points de vigilance connus](#annexe-b--points-de-vigilance-connus)
17. [Annexe C — Feuille de route des chantiers](#annexe-c--feuille-de-route-des-chantiers)

---

## 1 — État des lieux de la machine

Relevé effectué le 20 août 2026 sur la nouvelle machine.

| Élément | État | Détail |
| :--- | :---: | :--- |
| Python système | ✅ | 3.14.7 (`C:\Users\charles.nguessan\AppData\Local\Python\pythoncore-3.14-64`) |
| Environnement `.venv` | ✅ | Python 3.14.7, **toutes** les dépendances de `requirements.txt` déjà installées |
| PostgreSQL | ✅ | Version **17.11**, service `postgresql-x64-17` en cours d'exécution |
| `psql` dans le PATH | ❌ | Binaires présents dans `C:\Program Files\PostgreSQL\17\bin` |
| Base `cmu_simulator` | ❌ | **Absente** — seules `postgres`, `template0`, `template1` existent |
| Node.js / npm | ✅ | v26.7.0 / 11.19.0 |
| `dashboard/node_modules` | ❌ | Absent — à installer |
| Docker | ❌ | Non installé |

### Décision : on travaille en local, pas en Docker

**Pourquoi :** PostgreSQL 17 tourne déjà et le `.venv` est complet. Installer Docker
Desktop (plusieurs Go, redémarrage, activation de WSL2) serait un long détour pour
un résultat identique. Les correctifs Docker restent prévus au **chantier 3**, mais
ils ne bloquent pas le développement local.

### Ce qui est déjà fait — ne pas refaire

L'environnement virtuel `.venv` contient déjà les 15 dépendances de
`requirements.txt` et leurs dépendances transitives (≈55 paquets) :

| Rôle | Paquets installés |
| :--- | :--- |
| Persistance | `SQLAlchemy 2.0.52`, `alembic 1.19.1`, `asyncpg 0.31.0`, `psycopg 3.3.4` |
| API | `fastapi 0.141.1`, `pydantic 2.13.4`, `pydantic-settings 2.15.0`, `uvicorn 0.52.4` |
| Temps réel | `python-socketio 5.16.4`, `python-engineio 4.13.5`, `websockets 17.0.1` |
| Sécurité | `bcrypt 5.0.0`, `PyJWT 2.13.0`, `email-validator 2.3.0` |
| Rapports | `fpdf2 2.8.8`, `openpyxl 3.1.5`, `APScheduler 3.11.3` |
| Données de test | `Faker 40.36.0` |

👉 **Tu n'as donc PAS besoin de faire `pip install -r requirements.txt`.**

---

## 2 — Comprendre ce qu'on va faire et pourquoi

Avant de taper quoi que ce soit, voici l'architecture qu'on remet en place et
l'ordre logique des opérations.

### Ce que fait l'application

```
┌─────────────────────┐         ┌──────────────────────┐
│  Dashboard React    │◄───────►│  API FastAPI         │
│  localhost:5173     │  REST   │  127.0.0.1:8000      │
│  (dashboard/)       │  +WS    │  (api/, realtime/)   │
└─────────────────────┘         └──────────┬───────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                  │ Moteur de    │ │ Bus d'événe- │ │ PostgreSQL   │
                  │ simulation   │►│ ments +KPI   │►│ 17           │
                  │ (simulation/)│ │ (events/kpi/)│ │ cmu_simulator│
                  └──────────────┘ └──────────────┘ └──────────────┘
```

Le moteur simule des passages de soins d'assurés CMU. Chaque écriture métier
produit un **événement**, journalisé en base puis diffusé aux abonnés. Un
consommateur recalcule les KPI et les pousse au dashboard via Socket.IO.

### Pourquoi cet ordre d'étapes précis

Chaque étape dépend strictement de la précédente. Impossible d'inverser :

| Ordre | Étape | Dépend de |
| :---: | :--- | :--- |
| 1 | `psql` accessible | — |
| 2 | Base créée | 1 (il faut `psql` pour créer la base) |
| 3 | Venv + `DATABASE_URL` | 2 (l'URL doit pointer sur une base existante) |
| 4 | Schéma des tables | 3 (Alembic lit `DATABASE_URL`) |
| 5 | Compte admin | 4 (la table `TB_UTILISATEURS` doit exister) |
| 6 | Données référentielles | 4 (les tables `TB_REF_*` doivent exister) |
| 7 | API démarrée | 4 + 5 (elle interroge le schéma et authentifie) |
| 8 | Dashboard | 7 (il appelle l'API) |
| 9 | Connexion | 5 + 7 + 8 (identifiants + API + interface) |

---

## 3 — Le problème du fichier `.env`

### Le constat

Le fichier `.env` présent à la racine contient :

```ini
DATABASE_URL=postgresql+asyncpg://postgres:ancien_mot_de_passe@db:5432/cmu_simulator
```

**Deux problèmes rendent cette valeur inutilisable ici :**

| Problème | Explication |
| :--- | :--- |
| `@db:5432` | `db` est le **nom du service Docker** défini dans `docker-compose.yml`. Sans Docker, ce nom d'hôte ne résout pas. En local c'est `localhost`. |
| `ancien_mot_de_passe` | Ce mot de passe a été publié sur un dépôt GitHub public. Il est remplacé au chantier 1 (voir GUIDE_1_HYGIENE_GIT_SECRETS.md, partie A.3). |

### La solution retenue : ne pas toucher au fichier

On définit `DATABASE_URL` **dans la session PowerShell**. Cette variable
d'environnement a priorité sur tout le reste, par conception du projet :

| Fichier | Ligne | Code | Effet |
| :--- | :---: | :--- | :--- |
| `app/database.py` | 10 | `os.getenv("DATABASE_URL", "...")` | L'environnement gagne sur la valeur codée en dur |
| `alembic/env.py` | 19 | `os.getenv("DATABASE_URL", config.get_main_option(...))` | L'environnement gagne sur `alembic.ini` |
| `auth/security.py` | 14 | `os.environ.get("JWT_SECRET_KEY", "...")` | Idem pour la clé de signature JWT |

**Pourquoi ne pas simplement corriger `.env` ?**
Parce que `.env` est actuellement **suivi par git** et contient des secrets. Le
sortir du suivi et créer un `.gitignore` fait l'objet du **chantier 1**. Tant que
ce n'est pas fait, toute modification du fichier partirait dans l'historique git.
On évite donc de le toucher.

> ⚠️ **Conséquence pratique** : les variables de session disparaissent quand tu
> fermes le terminal. Il faudra les redéfinir à chaque démarrage — voir le
> [rituel de démarrage quotidien](#rituel-de-démarrage-quotidien).

---

## 4 — Vue d'ensemble des étapes

| # | Action | Fichiers du projet mis en jeu | Ce que ça produit |
| :---: | :--- | :--- | :--- |
| 1 | Rendre `psql` accessible | *(aucun)* | Commande `psql` utilisable |
| 2 | Créer la base | *(aucun)* | Base `cmu_simulator` vide |
| 3 | Venv + variables | `.venv/`, *(lues par)* `app/database.py`, `alembic/env.py`, `auth/security.py` | Session configurée |
| 4 | Migrations | `alembic.ini`, `alembic/env.py`, `alembic/versions/*.py`, `app/models/*.py`, `auth/models.py`, `events/models.py` | **24 tables** créées |
| 5 | Compte admin | `auth/bootstrap.py`, `auth/models.py`, `auth/security.py` | 1 ligne dans `TB_UTILISATEURS` |
| 6 | Seed | `seed/__main__.py`, `seed/runner.py`, `seed/constants.py`, `seed/anomalies.py` | ~100 500 lignes référentielles |
| 7 | API | `api/main.py`, `api/routers/*`, `realtime/`, `kpi/`, `events/`, `metrics/`, `reports/` | Serveur sur `:8000` |
| 8 | Dashboard | `dashboard/package.json`, `dashboard/vite.config.ts` | `node_modules/` + serveur `:5173` |
| 9 | Connexion | `dashboard/src/auth/*`, `dashboard/src/services/api.ts` | Application utilisable |

### Règles générales

- **Toutes les commandes se tapent depuis la racine du projet**
  (`C:\Users\charles.nguessan\Documents\simulateur_V5`), sauf mention contraire.
- **Étapes 1 à 7 : une seule et même fenêtre PowerShell.** Les variables de
  session sont perdues si tu fermes le terminal.
- **Arrête-toi au premier blocage** et remonte l'erreur complète.

---

## Étape 1 — Rendre `psql` accessible

### À quoi ça sert

`psql` est le client en ligne de commande de PostgreSQL. On en a besoin pour
**créer la base** (étape 2) et pour **vérifier** le contenu des tables après les
étapes 4 et 6. L'installateur PostgreSQL 17 ne l'ajoute pas au PATH système par
défaut.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `C:\Program Files\PostgreSQL\17\bin\psql.exe` | Le binaire client (hors projet) |

*Aucun fichier du projet n'est mis en jeu à cette étape.*

### Commandes

**1.1 — Ajouter les binaires PostgreSQL au PATH de la session :**

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\17\bin"
```

> **Pourquoi `$env:Path` et pas une modification permanente ?** Cette forme ne
> modifie le PATH que pour la fenêtre courante. Rien n'est changé durablement sur
> le système — cohérent avec le principe « on ne modifie rien sans nécessité ».

**1.2 — Vérifier que la commande répond :**

```powershell
psql --version
```

**1.3 — Corriger l'affichage des accents (optionnel mais confortable) :**

```powershell
chcp 65001
```

> La console Windows utilise par défaut le codage cp850, ce qui affiche
> `donnÚes` au lieu de `données`. `chcp 65001` bascule en UTF-8. Purement
> cosmétique, sans effet sur les données.

**1.4 — Enregistrer le mot de passe pour la session et tester la connexion.**
Remplace `TON_MOT_DE_PASSE` par le mot de passe que tu as défini pour
l'utilisateur `postgres` à l'installation de PostgreSQL 17 :

```powershell
$env:PGPASSWORD = "TON_MOT_DE_PASSE"
```

```powershell
psql -U postgres -h localhost -p 5432 -c "SELECT version();"
```

> **Pourquoi `PGPASSWORD` ?** Sans cette variable, `psql` ouvre une invite
> interactive de mot de passe à **chaque** commande. C'est une variable
> standard de PostgreSQL, valable pour la session uniquement.

### Résultat attendu

```
psql (PostgreSQL) 17.11
```

puis

```
                           version
------------------------------------------------------------
 PostgreSQL 17.11 on x86_64-windows, compiled by msvc-19...
(1 ligne)
```

### En cas d'erreur

| Message | Cause | Action |
| :--- | :--- | :--- |
| `psql : terme non reconnu` | Le PATH n'a pas été pris | Revérifier le chemin en 1.1, contrôler que `psql.exe` existe bien |
| `password authentication failed for user "postgres"` | Mauvais mot de passe | Le mot de passe est celui saisi à l'installation de PostgreSQL, pas celui du `.env`. Me remonter le cas si tu l'as perdu. |
| `could not connect to server` | Service arrêté | Vérifier avec `Get-Service postgresql*` — le statut doit être `Running` |

---

## Étape 2 — Créer la base de données

### À quoi ça sert

Créer le **conteneur logique vide** qui accueillera les 24 tables. À ce stade il
n'y a **aucune table** : le schéma sera construit par Alembic à l'étape 4.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `schema_initial.sql` | ⚠️ **NON utilisé.** Ce fichier de 35 Ko est un artefact de référence documentaire. La **source de vérité** du schéma, ce sont les 6 migrations Alembic. Ne le joue pas manuellement. |

*Aucun fichier du projet n'est exécuté à cette étape.*

### Commandes

**2.1 — Vérifier l'état actuel :**

```powershell
psql -U postgres -h localhost -c "\l"
```

> **Constat au 20/08/2026 :** seules `postgres`, `template0` et `template1`
> apparaissent. `cmu_simulator` est donc bien absente et doit être créée.

**2.2 — Créer la base :**

```powershell
psql -U postgres -h localhost -c "CREATE DATABASE cmu_simulator;"
```

> **Ce que fait PostgreSQL :** il clone `template1` (codage UTF8, locale `C`) pour
> produire une base vierge dont `postgres` est propriétaire.

**2.3 — Confirmer :**

```powershell
psql -U postgres -h localhost -c "\l"
```

### Résultat attendu

`CREATE DATABASE` en retour de la commande 2.2, puis **4 lignes** dans la liste,
avec `cmu_simulator` en tête.

### En cas d'erreur

| Message | Cause | Action |
| :--- | :--- | :--- |
| `database "cmu_simulator" already exists` | Elle existait déjà | Aucun problème, passe à l'étape 3 |
| `permission denied to create database` | Utilisateur non superutilisateur | Vérifier que tu es bien connecté en `postgres` |

---

## Étape 3 — Activer le venv et définir la connexion

### À quoi ça sert

Deux choses distinctes :

1. **Activer le `.venv`** : basculer sur l'interpréteur Python du projet, celui
   qui contient SQLAlchemy, FastAPI, etc. Sans ça, `python` pointe sur
   l'interpréteur système, où rien n'est installé.
2. **Définir les variables d'environnement** : indiquer au projet **où** est la
   base et **avec quelle clé** signer les jetons JWT — sans modifier de fichier.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `.venv\Scripts\Activate.ps1` | Script d'activation de l'environnement virtuel |
| `app/database.py` *(ligne 10)* | **Lit** `DATABASE_URL` — utilisé par l'API, le moteur et le seed |
| `alembic/env.py` *(ligne 19)* | **Lit** `DATABASE_URL` — utilisé par les migrations |
| `auth/security.py` *(ligne 14)* | **Lit** `JWT_SECRET_KEY` — signature des jetons |
| `.env` | ❌ **Volontairement ignoré** — voir [section 3](#3--le-problème-du-fichier-env) |
| `alembic.ini` *(ligne 7)* | ❌ Sa valeur `sqlalchemy.url` est **écrasée** par `DATABASE_URL` |

### Commandes

**3.1 — Activer l'environnement virtuel :**

```powershell
.\.venv\Scripts\Activate.ps1
```

Ton invite doit désormais commencer par `(.venv)`.

> **Si tu obtiens `l'exécution de scripts est désactivée sur ce système`**, tape
> d'abord la commande ci-dessous, puis relance l'activation :
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```
>
> Le `-Scope Process` limite l'effet à cette fenêtre : la politique de sécurité
> du système n'est pas modifiée.

**3.2 — Définir l'URL de connexion.** Remplace `TON_MOT_DE_PASSE` par le même
mot de passe qu'à l'étape 1 :

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:TON_MOT_DE_PASSE@localhost:5432/cmu_simulator"
```

**Décomposition de l'URL :**

| Fragment | Signification | Piège à éviter |
| :--- | :--- | :--- |
| `postgresql+asyncpg` | Dialecte SQLAlchemy **asynchrone** | Ne pas mettre `postgresql://` seul : le projet est full-async |
| `postgres:TON_MOT_DE_PASSE` | Utilisateur et mot de passe | Le mot de passe de **cette** machine |
| `@localhost` | Hôte | **Pas `db`** — c'est le nom Docker |
| `:5432` | Port | **Pas 5433** — le 5433 est le mapping du `docker-compose.yml` |
| `/cmu_simulator` | Base créée à l'étape 2 | — |

**3.3 — Définir la clé JWT :**

```powershell
$env:JWT_SECRET_KEY = "dev-local-provisoire-a-changer"
```

> **Pourquoi une valeur provisoire ?** La clé actuellement dans `.env` est
> **compromise** : elle est publiée dans l'historique git. Sa régénération propre
> fait partie du **chantier 1**. En attendant, cette valeur locale suffit pour
> développer.

**3.4 — Contrôler que les variables sont bien posées :**

```powershell
echo $env:DATABASE_URL
```

```powershell
python --version
```

### Résultat attendu

- L'invite affiche `(.venv)`
- `echo` renvoie l'URL complète avec `localhost:5432`
- `python --version` renvoie `Python 3.14.7`

---

## Étape 4 — Construire le schéma (Alembic)

### À quoi ça sert

C'est **l'étape structurante** : elle crée les 24 tables de la base à partir des
migrations versionnées. Alembic applique les révisions dans l'ordre et note dans
une table `alembic_version` où il en est — l'opération est donc **idempotente**
(la relancer ne casse rien).

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `alembic.ini` | Configuration : `script_location`, journalisation. Sa clé `sqlalchemy.url` est écrasée par `DATABASE_URL`. |
| `alembic/env.py` | Point d'entrée : lit `DATABASE_URL`, ouvre le moteur async, exécute les révisions |
| `alembic/versions/20260814_0001_schema_initial.py` | Schéma initial : référentiels, factures, ententes |
| `alembic/versions/20260814_0002_agent_entente_nullable.py` | Rend l'entente préalable facultative sur la facture |
| `alembic/versions/20260814_0003_journal_evenements.py` | Crée `TB_EVENEMENTS_METIER` (journal d'événements) |
| `alembic/versions/20260814_0004_utilisateurs.py` | Crée `TB_UTILISATEURS` (comptes du dashboard) |
| `alembic/versions/20260814_0005_config_anomalies.py` | Configuration des anomalies |
| `alembic/versions/20260814_0006_assure_identite_regime.py` | Identité et régime de l'assuré |
| `app/models/base.py` | Base déclarative + colonnes d'audit communes |
| `app/models/schema.py` | Les 22 modèles métier (787 lignes) |
| `auth/models.py` | Modèle `User` |
| `events/models.py` | Modèle `EventJournal` |

### Commandes

**4.1 — Voir l'état actuel des migrations (facultatif mais instructif) :**

```powershell
python -m alembic current
```

> Sur une base neuve, la sortie est vide : aucune révision n'est appliquée.

**4.2 — Appliquer toutes les migrations :**

```powershell
python -m alembic upgrade head
```

> `head` signifie « la révision la plus récente ». Alembic remonte la chaîne des
> 6 révisions et les applique dans l'ordre.

**4.3 — Vérifier que les tables existent :**

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "\dt"
```

**4.4 — Compter les tables créées :**

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
```

### Résultat attendu

Une série de lignes du type :

```
INFO  [alembic.runtime.migration] Running upgrade  -> 20260814_0001, schema_initial
INFO  [alembic.runtime.migration] Running upgrade 20260814_0001 -> 20260814_0002, ...
```

Puis, au comptage : **25** (les 24 tables métier + `alembic_version`).

### En cas d'erreur

> ⚠️ **C'est ici que se joue la compatibilité Python 3.14.** Le projet a été
> développé sous Python 3.12 (les `__pycache__` versionnés portent le suffixe
> `cpython-312`). Cette étape est la première à exécuter réellement du code
> asynchrone du projet (SQLAlchemy + asyncpg + asyncio).

| Message | Cause probable | Action |
| :--- | :--- | :--- |
| `password authentication failed` | Mot de passe erroné dans `DATABASE_URL` | Revoir l'étape 3.2 |
| `database "cmu_simulator" does not exist` | Étape 2 non faite ou nom mal orthographié | Revoir l'étape 2 |
| `Can't load plugin: sqlalchemy.dialects:postgresql.asyncpg` | Venv non activé | Revoir l'étape 3.1 |
| Trace Python quelconque | Possible incompatibilité 3.14 | **Ne pas bricoler.** Copier la trace **complète** et me la remonter. |

---

## Étape 5 — Créer le compte administrateur

### À quoi ça sert

Créer le **premier compte** permettant de se connecter au dashboard. Sans lui,
la page de login refuse tout accès et l'application est inutilisable.

Le projet définit trois rôles hiérarchiques (`auth/dependencies.py`, ligne 20) :

| Rôle | Niveau | Droits |
| :--- | :---: | :--- |
| `observateur` | 0 | Lecture seule |
| `operateur` | 1 | + piloter la simulation, générer les rapports |
| `administrateur` | 2 | + gérer les utilisateurs, configurer les anomalies |

Le script `bootstrap` crée d'office un compte `administrateur`.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `auth/bootstrap.py` | Le script interactif exécuté |
| `auth/models.py` | Modèle `User` → table `TB_UTILISATEURS` |
| `auth/security.py` | `hash_password()` — hachage bcrypt avec sel unique |
| `app/database.py` | Fournit la session de base de données |

### Commandes

**5.1 — Lancer le script :**

```powershell
python -m auth.bootstrap
```

**5.2 — Répondre aux trois questions :**

```
Email de l'administrateur : ton.email@exemple.ci
Nom complet : Charles N'Guessan
Mot de passe (8 caractères minimum) : ........
```

> ⚠️ **Deux avertissements importants**
>
> 1. **Note ce mot de passe.** Il n'est **pas récupérable** : seul son haché
>    bcrypt est stocké en base (`auth/security.py`, ligne 19).
> 2. **Le mot de passe s'affichera en clair à l'écran.** Le script utilise
>    `input()` au lieu de `getpass()` (`auth/bootstrap.py`, ligne 41). C'est un
>    défaut mineur que je te proposerai de corriger plus tard. Assure-toi que
>    personne ne regarde ton écran.

**5.3 — Vérifier la création :**

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT \"EMAIL\", \"ROLE\", \"STATUT_ACTIF\" FROM \"TB_UTILISATEURS\";"
```

> **Pourquoi tous ces guillemets ?** Les noms de tables et colonnes du projet
> sont en **majuscules**. PostgreSQL les met en minuscules par défaut, sauf s'ils
> sont entre guillemets doubles. En PowerShell, ces guillemets doivent être
> échappés par un antislash (`\"`).

### Résultat attendu

```
Compte administrateur créé pour ton.email@exemple.ci.
```

et une ligne en base avec `role = administrateur` et `statut_actif = t`.

### En cas d'erreur

| Message | Cause | Action |
| :--- | :--- | :--- |
| `Un compte existe déjà pour ...` | Email déjà utilisé | Le compte existe, passe à l'étape 6 |
| `Mot de passe trop court, opération annulée.` | Moins de 8 caractères | Relance le script |
| `relation "TB_UTILISATEURS" does not exist` | Étape 4 incomplète | Relancer `python -m alembic upgrade head` |

---

## Étape 6 — Charger les données référentielles (seed)

### À quoi ça sert

Remplir les tables `TB_REF_*` avec les données de base **sans lesquelles le
moteur de simulation ne peut pas fonctionner**. Le moteur tire au sort un centre,
un professionnel, une pathologie, un médicament à chaque passage
(`simulation/passage.py`) : si les référentiels sont vides, il lève
`Référentiel vide pour ...` et tous les passages échouent.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `seed/__main__.py` | Point d'entrée `python -m seed` ; lit `ANOMALIES_ENABLED` / `ANOMALIES_RATE` |
| `seed/runner.py` | Génération et insertion par lots (`upsert_rows`) |
| `seed/constants.py` | Villes ivoiriennes, noms, actes médicaux, spécialités, pathologies |
| `seed/anomalies.py` | Injection optionnelle de données incohérentes (désactivée par défaut) |
| `app/models/schema.py` | Les modèles cibles de l'insertion |

### Volumes générés

| Données | Volume | Table |
| :--- | ---: | :--- |
| Centres de santé | 30 | `TB_REF_CENTRES_SANTE` |
| Agents (50 accueil + 10 médecins conseils) | 60 | `TB_REF_AGENTS` |
| Professionnels de santé (100 médecins + 50 infirmiers) | 150 | `TB_REF_PROFESSIONNELS_SANTE` |
| Pathologies | 100 | `TB_REF_PATHOLOGIES` |
| Médicaments, actes, spécialités | référentiels | `TB_REF_*` |
| **Assurés** | **100 000** | `TB_REF_ASSURES` |

### Commandes

**6.1 — Lancer le seed :**

```powershell
python -m seed
```

> **⏱️ Sois patient.** Les 100 000 assurés sont insérés par lots de 500, soit
> **200 lots**. Tu verras défiler des lignes
> `Lot 1/200 : 500 lignes upsertées pour TB_REF_ASSURES.` Compte plusieurs
> minutes selon la machine.

> **Le seed est idempotent.** Il utilise `INSERT ... ON CONFLICT DO UPDATE`
> (`seed/runner.py`, fonction `upsert_rows`). Tu peux l'interrompre par `Ctrl+C`
> et le relancer : il met à jour au lieu de dupliquer.

> **Déterminisme.** Les identifiants sont générés par `uuid5` et par une
> transformation modulaire bijective pour les numéros de sécurité sociale
> (`seed/runner.py`, lignes 180-195). Un même index produit toujours le même
> assuré : deux exécutions donnent des données identiques.

**6.2 — Vérifier les volumes :**

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT count(*) FROM \"TB_REF_ASSURES\";"
```

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT count(*) FROM \"TB_REF_CENTRES_SANTE\";"
```

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT count(*) FROM \"TB_REF_PROFESSIONNELS_SANTE\";"
```

### Résultat attendu

```
✓ Seed complété. Aucune anomalie.
```

Et aux comptages : **100000**, **30**, **150**.

### En cas d'erreur

| Message | Cause | Action |
| :--- | :--- | :--- |
| `relation "TB_REF_..." does not exist` | Étape 4 incomplète | Relancer les migrations |
| `too many arguments for query` | Limite asyncpg de 32767 paramètres | Ne devrait pas arriver : le découpage en lots de 500 est prévu. Me remonter le cas. |
| Interruption en cours de route | — | Relance simplement `python -m seed` |

---

## Étape 7 — Démarrer l'API

### À quoi ça sert

Lancer le serveur ASGI qui expose :

- l'**API REST** (KPI, factures, centres, utilisateurs, rapports, métriques) ;
- le **canal Socket.IO** temps réel sur le namespace `/kpi` ;
- le **moteur de simulation**, piloté par les routes `/simulation/*`.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `api/main.py` | Assemble FastAPI + Socket.IO, CORS, middleware de chronométrage, cycle de vie |
| `api/routers/simulation.py` | `/simulation/start`, `/stop`, `/speed`, `/status` |
| `api/routers/kpi.py` | `/kpi/snapshot`, `/kpi/{nom}/history` |
| `api/routers/metrics.py` | `/metrics/technical` — alimente les cartes du dashboard |
| `api/routers/auth.py` | `/auth/login` — émission du jeton JWT |
| `api/routers/users.py` | `/users` — gestion des comptes (admin) |
| `api/routers/reports.py` | `/reports` — génération et téléchargement |
| `api/routers/anomalies.py` | `/anomalies` — configuration du chaos testing |
| `api/routers/centres.py`, `factures.py` | Consultation du référentiel et des factures |
| `api/services/simulation_manager.py` | Instance unique du moteur, sérialise start/stop |
| `realtime/socket_server.py` | Serveur Socket.IO, namespace `/kpi` |
| `events/bus.py`, `events/models.py` | Bus d'événements + journalisation |
| `kpi/consumer.py`, `kpi/service.py` | Recalcul et diffusion des KPI |
| `metrics/registry.py` | Registre des métriques techniques |
| `reports/scheduler.py` | Planificateur APScheduler (rapport quotidien à minuit) |
| `simulation_config.py` | Probabilités et durées du moteur |

### Commandes

**7.1 — Démarrer le serveur** (dans la **même fenêtre** que les étapes 3 à 6, les
variables `DATABASE_URL` et `JWT_SECRET_KEY` doivent être présentes) :

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

**Décomposition :**

| Argument | Rôle |
| :--- | :--- |
| `api.main:app` | L'objet ASGI, qui est le **wrapper Socket.IO** englobant FastAPI (`api/main.py`, dernière ligne) |
| `--reload` | Redémarre automatiquement à chaque modification de fichier — pratique en développement |
| `--host 127.0.0.1` | N'écoute que la machine locale |
| `--port 8000` | Port attendu par le dashboard (`VITE_API_URL`) |

> **⚠️ Cette fenêtre reste occupée.** L'API tourne dedans. Ouvre un **second
> terminal** pour l'étape 8.

**7.2 — Vérifier dans le navigateur :**

| URL | Attendu |
| :--- | :--- |
| <http://127.0.0.1:8000/health> | `{"statut":"ok"}` |
| <http://127.0.0.1:8000/docs> | Documentation Swagger avec toutes les routes |
| <http://127.0.0.1:8000/metrics/technical> | JSON de métriques techniques |

### Résultat attendu

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

### En cas d'erreur

| Message | Cause | Action |
| :--- | :--- | :--- |
| `[Errno 10048] address already in use` | Le port 8000 est déjà pris | Fermer l'autre instance, ou utiliser `--port 8001` (il faudra alors adapter `VITE_API_URL`) |
| `ModuleNotFoundError` | Venv non activé | Revoir l'étape 3.1 |
| Erreur de connexion base au démarrage | `DATABASE_URL` absente de la session | Revoir l'étape 3.2 |

---

## Étape 8 — Installer et démarrer le dashboard

### À quoi ça sert

Installer les dépendances npm (absentes) puis lancer le serveur de développement
Vite qui sert l'interface React.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `dashboard/package.json` | Déclare React 19, Recharts, socket.io-client, Vite 8, TypeScript 6 |
| `dashboard/package-lock.json` | Verrouille les versions exactes |
| `dashboard/vite.config.ts` | Configuration du serveur : `host 0.0.0.0`, port `5173`, polling |
| `dashboard/index.html` | Point d'entrée HTML |
| `dashboard/src/main.tsx` | Montage React |
| `dashboard/node_modules/` | **Créé par l'installation** (absent aujourd'hui) |

### Commandes

**8.1 — Dans un SECOND terminal**, se placer dans le dossier du dashboard :

```powershell
cd C:\Users\charles.nguessan\Documents\simulateur_V5\dashboard
```

**8.2 — Installer les dépendances :**

```powershell
npm install --legacy-peer-deps
```

> **Pourquoi `--legacy-peer-deps` ?** React 19 est récent et certaines
> dépendances (notamment Recharts 2.x) déclarent encore React 18 en *peer
> dependency*. Sans ce drapeau, npm refuse l'installation. C'est exactement ce
> que fait le projet dans `docker-compose.yml` (ligne 86) et
> `dashboard/Dockerfile`.

> ℹ️ Cette commande crée `dashboard/node_modules/` (plusieurs centaines de Mo) et
> peut prendre quelques minutes. Des avertissements `deprecated` sont normaux.

**8.3 — Démarrer le serveur de développement :**

```powershell
npm run dev
```

> **Note sur `VITE_API_URL` :** cette variable n'est pas définie dans ta session.
> Ce n'est pas grave : `dashboard/src/services/api.ts` (ligne 5) prévoit la
> valeur de repli `http://127.0.0.1:8000`, qui correspond exactement à l'API
> lancée à l'étape 7.

### Résultat attendu

```
VITE v8.x.x  ready in 512 ms

➜  Local:   http://localhost:5173/
➜  Network: http://192.168.x.x:5173/
```

### En cas d'erreur

| Message | Cause | Action |
| :--- | :--- | :--- |
| `ERESOLVE unable to resolve dependency tree` | Drapeau oublié | Relancer avec `--legacy-peer-deps` |
| `Port 5173 is already in use` | Instance déjà lancée | Vite propose le port 5174 — mais il faudra alors adapter `CORS_ORIGINS` |
| `tsc` errors | Erreurs TypeScript | `npm run dev` ne type-check pas ; si c'est `npm run build`, me remonter la trace |

---

## Étape 9 — Se connecter et vérifier

### À quoi ça sert

Valider **bout en bout** que la chaîne complète fonctionne : navigateur →
dashboard → API → base de données.

### Fichiers concernés

| Fichier | Rôle |
| :--- | :--- |
| `dashboard/src/auth/LoginPage.tsx` | Formulaire de connexion |
| `dashboard/src/auth/AuthContext.tsx` | Appelle `/auth/login`, stocke le jeton en `localStorage` |
| `dashboard/src/auth/RequireRole.tsx` | Masque les sections selon le rôle |
| `dashboard/src/App.tsx` | Coquille du tableau de bord, sondage `/metrics/technical` toutes les 1,5 s |
| `dashboard/src/services/api.ts` | Tous les appels HTTP et l'en-tête `Authorization` |
| `dashboard/src/hooks/useKpiSocket.tsx` | Connexion Socket.IO + repli REST |
| `dashboard/src/components/TechMetricCards.tsx` | Cartes de métriques (rangée 1) |
| `dashboard/src/components/LiveLogTerminal.tsx` | Console de logs (rangée 4) |

### Marche à suivre

**9.1 —** Ouvrir <http://localhost:5173>

**9.2 —** Saisir l'email et le mot de passe créés à l'étape 5.

**9.3 —** Vérifier les points suivants :

| Élément | Attendu |
| :--- | :--- |
| Cartes de métriques (haut) | Se rafraîchissent toutes les 1,5 s |
| Bouton **Démarrer** (barre supérieure) | Lance le moteur — les compteurs augmentent |
| Onglet **Utilisateurs** | Visible (tu es `administrateur`) |
| Onglet **Rapports** | Visible et fonctionnel |
| Panneau **Anomalies** | Visible |
| Terminal de logs (bas) | Défile pendant la simulation |

### ⚠️ Ce qui ne fonctionnera PAS — et c'est normal

**Le badge de connexion temps réel restera sur `deconnecte` ou `reconnexion`.**

| Détail | Valeur |
| :--- | :--- |
| Fichier en cause | `realtime/socket_server.py`, ligne 8 |
| Code fautif | `sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])` |
| Explication | Une **liste vide** n'autorise **aucune** origine. Le dashboard sur `localhost:5173` parlant à l'API sur `127.0.0.1:8000` est cross-origin : le handshake est rejeté. |
| Correctif prévu | **Chantier 3** |
| Impact | Les métriques techniques passent par REST et fonctionnent quand même |

De même, le **panneau « Chaos Testing / Anomalies »** répondra sans erreur mais
**n'aura aucun effet sur le moteur** : `seed/anomalies.py` n'est consommé que par
le seed, jamais par `simulation/passage.py`. Correctif prévu au **chantier 5**.

---

## Rituel de démarrage quotidien

Une fois le chantier 0 terminé, voici ce qu'il faudra retaper à chaque session.

### Terminal 1 — API

```powershell
cd C:\Users\charles.nguessan\Documents\simulateur_V5
```

```powershell
.\.venv\Scripts\Activate.ps1
```

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:TON_MOT_DE_PASSE@localhost:5432/cmu_simulator"
```

```powershell
$env:JWT_SECRET_KEY = "dev-local-provisoire-a-changer"
```

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 — Dashboard

```powershell
cd C:\Users\charles.nguessan\Documents\simulateur_V5\dashboard
```

```powershell
npm run dev
```

> 💡 **Au chantier 1**, je te proposerai un fichier `.env.local` **non versionné**
> et un petit script de démarrage, pour ne plus avoir à retaper ces variables.

---

## Annexe A — Les 24 tables du schéma

Créées par l'étape 4. Noms exacts relevés dans les modèles SQLAlchemy.

### Référentiels — `app/models/schema.py`

| Table | Contenu |
| :--- | :--- |
| `TB_REF_ASSURES` | Assurés CMU (100 000 après seed) |
| `TB_REF_CENTRES_SANTE` | Centres de santé (30) |
| `TB_REF_AGENTS` | Agents d'accueil et médecins conseils (60) |
| `TB_REF_PROFESSIONNELS_SANTE` | Médecins et infirmiers (150) |
| `TB_REF_SPECIALITES_MEDICALES` | Spécialités |
| `TB_REF_PATHOLOGIES` | Pathologies (100) |
| `TB_REF_MEDICAMENTS` | Médicaments |
| `TB_REF_ACTES_MEDICAUX` | Actes (`BIO-`, `IMG-`, `HOS-`, consultations) |
| `TB_TV_TYPES_FACTURES` | Types de factures (`AMB`, `DEN`) |

### Associations

| Table | Contenu |
| :--- | :--- |
| `TB_CENTRES_SANTE_AGENTS` | Affectation des agents aux centres |
| `TB_PROFESSIONNELS_SANTE_CENTRES_SANTE` | Affectation des professionnels |
| `TB_REF_PROFESSIONNELS_SANTE_SPECIALITES_MEDICALES` | Spécialités des médecins |

### Factures — alimentées par la simulation

| Table | Contenu |
| :--- | :--- |
| `TB_FACTURES` | En-tête de facture |
| `TB_FACTURES_PATHOLOGIES` | Diagnostics rattachés |
| `TB_FACTURES_PRESCRIPTIONS` | Médicaments prescrits |
| `TB_FACTURES_PRESTATIONS` | Prestations servies |
| `TB_FACTURES_STATUTS` | Cycle de vie (`ouverte` → `cloturee`) |
| `TB_FACTURES_REJETS` | Rejets |

### Ententes préalables

| Table | Contenu |
| :--- | :--- |
| `TB_ENTENTES_PREALABLES` | Demandes d'accord préalable |
| `TB_ENTENTES_PREALABLES_STATUTS` | Décisions (`acceptee`, `refusee`, `validee_office`) |
| `TB_ENTENTES_PREALABLES_ACTES_MEDICAUX` | Actes demandés et montants |
| `TB_ENTENTES_PREALABLES_PRESTATIONS` | Prestations liées |

### Techniques

| Table | Contenu | Fichier |
| :--- | :--- | :--- |
| `TB_UTILISATEURS` | Comptes du dashboard | `auth/models.py` |
| `TB_EVENEMENTS_METIER` | Journal d'événements (JSONB) | `events/models.py` |
| `alembic_version` | Révision Alembic courante | *(géré par Alembic)* |

---

## Annexe B — Points de vigilance connus

Ces éléments sont **identifiés et planifiés**. Ils ne bloquent pas le chantier 0.

| # | Point | Fichier | Chantier |
| :---: | :--- | :--- | :---: |
| 1 | `.env` versionné avec la clé JWT et le mot de passe en clair ; aucun `.gitignore` à la racine | `.env` | 1 |
| 2 | Fichiers `.pyc` et dossier `.idea/` versionnés | `__pycache__/`, `.idea/` | 1 |
| 3 | `dockerfile` en minuscule → `docker build` échoue sur Linux (CI) | `dockerfile` | 3 |
| 4 | `COPY alembic.ini alembic/ ./` aplatit le dossier `alembic/` dans l'image | `dockerfile` ligne 22 | 3 |
| 5 | `cors_allowed_origins=[]` bloque tout Socket.IO | `realtime/socket_server.py` ligne 8 | 3 |
| 6 | Doublon de fichier compose (faute de frappe) | `docker-compse.yml` | 2 |
| 7 | Fonction `run()` définie deux fois | `run_simulation.py` lignes 24 et 34 | 2 |
| 8 | `/metrics/technical/reset` mutatif et non authentifié | `api/routers/metrics.py` | 4 |
| 9 | Panneau anomalies sans effet sur le moteur | `seed/anomalies.py` | 5 |
| 10 | Recalcul KPI en O(fenêtre) — recharge tous les événements 24 h à chaque snapshot | `kpi/service.py` | 6 |
| 11 | Mot de passe affiché en clair au bootstrap (`input()` au lieu de `getpass()`) | `auth/bootstrap.py` ligne 41 | 4 |
| 12 | Aucun test automatisé ; `test_realtime.py` est un script manuel | `test_realtime.py` | 7 |
| 13 | Python 3.14 alors que le projet a été développé en 3.12 | *(global)* | à surveiller |
| 14 | Pas de `pool_size` configuré : ~10 sessions par passage × 20 passages concurrents | `app/database.py` | 6 |

---

## Annexe C — Feuille de route des chantiers

| # | Chantier | État |
| :---: | :--- | :---: |
| **0** | **Remise en route sur la nouvelle machine** | 🔵 **en cours** |
| 1 | Hygiène git & secrets (`.gitignore`, sortir `.env`, régénérer la clé JWT) | ⚪ à faire |
| 2 | Nettoyage des doublons (`docker-compse.yml`, `run()`, imports morts) | ⚪ à faire |
| 3 | Réparer Docker (`Dockerfile`, `COPY alembic/`, CORS Socket.IO) | ⚪ à faire |
| 4 | Sécuriser les endpoints (`/metrics/.../reset`, `getpass`) | ⚪ à faire |
| 5 | Brancher les anomalies sur le moteur (ou corriger la documentation) | ⚪ à faire |
| 6 | Performance des KPI (agrégations SQL, pool de connexions) | ⚪ à faire |
| 7 | Tests automatisés (pytest + intégration CI) | ⚪ à faire |

---

## Ce qu'il faut me remonter

Avance **étape par étape** et **arrête-toi au premier blocage**. Pour chaque
problème, transmets :

1. La commande exacte tapée
2. Le message d'erreur **complet** (toute la trace, pas seulement la dernière ligne)
3. L'étape et le numéro de sous-commande (ex. « étape 4.2 »)

Les deux points où un accroc est le plus probable :

- **Étape 4** — les migrations, à cause de Python 3.14 vs 3.12
- **Étape 9** — le temps réel Socket.IO, bug connu et attendu

---

*Guide rédigé pour le projet `simulateur_V5` — chantier 0/7.*
