# GUIDE 3 — Réparer Docker et le temps réel

> **Chantier 3 sur 8** du plan de remise en ordre du projet `simulateur_V5`.
> Prérequis : [GUIDE_2_NETTOYAGE_DOUBLONS.md](./GUIDE_2_NETTOYAGE_DOUBLONS.md) terminé (commit `7ef5a3c` poussé).

---

## En deux mots

Trois défauts empêchent le projet de fonctionner **ailleurs que sur ta machine Windows** :

1. Le fichier `dockerfile` s'appelle avec un **d minuscule** → la CI GitHub Actions ne le trouve pas
2. Une ligne `COPY` **éparpille** les migrations Alembic dans l'image Docker → l'API ne démarre pas en production
3. Le serveur Socket.IO **n'autorise aucune origine** → c'est le badge « déconnecté » que tu vois depuis le chantier 0

Le troisième point est le seul **visible** aujourd'hui. Les deux premiers sont invisibles en local et casseraient au premier déploiement.

**Un point important :** ces trois bugs ne se manifestent pas chez toi. Windows ignore la casse des noms de fichiers, et tu n'as pas Docker. Ils n'en sont pas moins réels — la CI tourne sous Linux.

---

## Table des matières

- [Reste du chantier 2](#reste-du-chantier-2)
- [Partie A — Le nom du Dockerfile](#partie-a--le-nom-du-dockerfile)
- [Partie B — Les migrations éparpillées dans l'image](#partie-b--les-migrations-éparpillées-dans-limage)
- [Partie C — Le temps réel bloqué (CORS Socket.IO)](#partie-c--le-temps-réel-bloqué-cors-socketio)
- [Partie D — Normaliser les fins de ligne](#partie-d--normaliser-les-fins-de-ligne)
- [Partie E — Vérifier et commiter](#partie-e--vérifier-et-commiter)
- [Récapitulatif](#récapitulatif)

---

## Reste du chantier 2

Deux corrections du guide précédent n'ont pas été appliquées et sont parties dans le commit `7ef5a3c`. **Elles ne cassent rien** — l'import fonctionne — mais elles sont à reprendre.

### R.1 — `api/__init__.py` : restaurer

Ce fichier a reçu le contenu destiné à `api/routers/__init__.py`. **Remplace tout son contenu par cette unique ligne :**

```python
"""Initialise la couche API du simulateur CMU."""
```

> **Pourquoi c'est gênant :** en l'état, toucher au paquet `api` déclenche l'import de tous les routers, donc des modèles SQLAlchemy et de la base. Et sa docstring annonce « Regroupe les routers HTTP », ce qui est le rôle de l'autre fichier.

### R.2 — `api/routers/__init__.py` : retirer l'import mort

**Supprime la ligne 4 :**

```python
from api.schema import HealthResponse
```

Le fichier doit finir ainsi :

```python
"""Regroupe les routers HTTP du simulateur."""

from api.routers import centres, factures, kpi, simulation

__all__ = ["centres", "factures", "kpi", "simulation"]
```

---

## Partie A — Le nom du Dockerfile

**Fichier :** `dockerfile` → à renommer en `Dockerfile`

### Le problème

Le fichier à la racine s'appelle `dockerfile`, avec un **d minuscule**. Or :

| Qui le cherche | Sous quel nom |
|---|---|
| `docker-compose.yml:36` | `dockerfile: Dockerfile` (D majuscule) |
| `.github/workflows/ci.yml:106` | `docker build .` → cherche `Dockerfile` par défaut |
| `.github/workflows/deploy.yml` | idem |

**Sous Windows, ça marche** : le système de fichiers ignore la casse, `dockerfile` et `Dockerfile` désignent le même fichier.

**Sous Linux, ça échoue.** Les runners GitHub Actions tournent sous Ubuntu : `docker build .` cherche exactement `Dockerfile`, ne le trouve pas, et le job `docker-build` de la CI échoue. Le pipeline de déploiement ne peut donc produire aucune image.

### La correction

⚠️ **Ne renomme pas depuis l'explorateur Windows.** Comme la casse est ignorée, git ne verrait aucun changement. Il faut passer par git, qui gère la casse explicitement :

```powershell
git mv dockerfile Dockerfile.tmp
```

```powershell
git mv Dockerfile.tmp Dockerfile
```

> **Pourquoi en deux temps ?** git refuse de renommer `dockerfile` en `Dockerfile` directement sur un système insensible à la casse : pour lui, la cible existe déjà. Le passage par un nom intermédiaire contourne le blocage.

### Vérifier

```powershell
git ls-files | Select-String -Pattern "^Dockerfile$"
```

Attendu : `Dockerfile`

```powershell
git ls-files | Select-String -Pattern "^dockerfile$"
```

Attendu : **aucune sortie**

---

## Partie B — Les migrations éparpillées dans l'image

**Fichier :** `Dockerfile` ligne 18

### Le problème

```dockerfile
COPY alembic.ini alembic/ ./
```

Cette ligne a l'air correcte. Elle ne l'est pas.

**Règle Docker :** quand `COPY` reçoit **plusieurs sources** et un dossier comme destination, il copie le **contenu** de chaque dossier source, pas le dossier lui-même.

Résultat dans l'image :

| Fichier d'origine | Où il atterrit | Où il devrait être |
|---|---|---|
| `alembic.ini` | `/app/alembic.ini` | ✅ correct |
| `alembic/env.py` | `/app/env.py` | ❌ `/app/alembic/env.py` |
| `alembic/versions/*.py` | `/app/versions/*.py` | ❌ `/app/alembic/versions/*.py` |

Or `alembic.ini:4` déclare `script_location = %(here)s/alembic`. Alembic cherche donc `/app/alembic/`, un dossier qui **n'existe pas** dans l'image.

**Conséquence :** `scripts/docker-entrypoint.sh` exécute `alembic upgrade head` au démarrage. Cette commande échoue, l'entrypoint s'arrête (`set -e`), et **le conteneur ne démarre jamais**.

**Pourquoi personne ne l'a vu :** en développement, `docker-compose.yml:71` monte `./alembic:/app/alembic` par-dessus. Le volume masque le défaut. Il n'apparaît qu'en production, où il n'y a pas de volume.

### La correction

**Remplace la ligne 18 :**

```dockerfile
COPY alembic.ini alembic/ ./
```

**Par ces deux lignes :**

```dockerfile
COPY alembic.ini ./
COPY alembic/ ./alembic/
```

**Pourquoi ça marche :** avec **une seule source** et une destination qui se termine par `/`, Docker recrée l'arborescence complète. `alembic/versions/0001.py` devient bien `/app/alembic/versions/0001.py`.

---

## Partie C — Le temps réel bloqué (CORS Socket.IO)

**Fichier :** `realtime/socket_server.py` ligne 8

> 🎯 **C'est la correction qui rendra le dashboard pleinement fonctionnel.**

### Le problème

```python
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])
```

Une **liste vide n'autorise aucune origine**. Ce n'est pas « pas de restriction », c'est « tout est refusé ».

> Le défaut de `python-socketio` est `'*'` (tout autoriser). En passant explicitement `[]`, on a fait l'inverse de l'intention.

Le navigateur charge le dashboard depuis `http://localhost:5173` et ouvre une connexion vers `http://127.0.0.1:8000`. **Origines différentes** — même machine, mais ni le port ni le nom d'hôte ne correspondent. Le serveur inspecte l'en-tête `Origin`, ne le trouve dans aucune liste autorisée, et rejette la poignée de main.

**C'est la cause exacte du badge « déconnecté »** observé au chantier 0.

### La correction

FastAPI gère déjà ce problème proprement, dans `api/main.py` lignes 45-50 :

```python
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
_cors_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]
```

On applique la **même logique** à Socket.IO, plutôt que d'écrire `'*'` qui désactiverait toute protection.

**Remplace le début de `realtime/socket_server.py` :**

```python
"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

import socketio
from events import event_bus
from kpi import KpiConsumer, KpiService
from metrics.registry import registry as metrics_registry

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])
```

**Par :**

```python
"""Configure le serveur Socket.IO ASGI et le namespace KPI."""

import os

import socketio
from events import event_bus
from kpi import KpiConsumer, KpiService
from metrics.registry import registry as metrics_registry

# Mêmes origines que le middleware CORS de FastAPI (api/main.py), pour qu'une
# seule variable d'environnement pilote REST et temps réel.
_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
_cors_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_cors_origins)
```

**Ce que ça change :** `CORS_ORIGINS` pilote désormais REST **et** temps réel. Une seule variable, un seul endroit à modifier lors d'un déploiement.

### Vérifier

Démarre l'API :

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Dans un second terminal :

```powershell
cd dashboard
```

```powershell
npm run dev
```

Ouvre <http://localhost:5173>, connecte-toi, et **regarde le badge de connexion** : il doit passer à **`connecté`**.

Clique ensuite sur **Démarrer** : les graphiques doivent se mettre à jour en direct, sans rechargement de page.

> Si le badge reste rouge, ouvre la console du navigateur (`F12`) : un message mentionnant `Origin` confirmerait qu'une origine manque dans `CORS_ORIGINS`.

---

## Partie D — Normaliser les fins de ligne

**Fichier à créer :** `.gitattributes` (à la racine)

### Le problème

Au chantier 2, `metrics/registry.py` est apparu avec **304 lignes modifiées** alors qu'**une seule** avait changé. Ton éditeur avait converti tout le fichier de fins de ligne Unix (`LF`) vers Windows (`CRLF`).

Deux conséquences :

- **Les diffs deviennent illisibles** — impossible de relire un changement noyé dans 300 lignes de bruit
- **Les scripts shell cassent sous Linux** — un `.sh` en `CRLF` produit `bad interpreter: /bin/bash^M`

Le projet contourne déjà le second point à la main, dans le `Dockerfile` :

```dockerfile
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh
```

Ce `sed` est un pansement. Le `.gitattributes` traite la cause.

### La correction

**Contenu du fichier `.gitattributes` :**

```gitattributes
# Normalise les fins de ligne : LF dans le dépôt, quelle que soit la machine.
* text=auto eol=lf

# Fichiers qui DOIVENT rester en LF (exécutés sous Linux).
*.sh text eol=lf
Dockerfile text eol=lf
*.yml text eol=lf
*.yaml text eol=lf

# Fichiers binaires : ne jamais convertir.
*.png binary
*.jpg binary
*.jpeg binary
*.svg text
*.ico binary
*.pdf binary
*.xlsx binary
```

### Appliquer la normalisation aux fichiers existants

Créer le fichier ne suffit pas : les fichiers déjà en `CRLF` dans le dépôt doivent être réécrits.

```powershell
git add --renormalize .
```

```powershell
git status --short
```

Tu verras probablement `metrics/registry.py` et quelques autres. **C'est normal** — c'est la normalisation qui opère.

> **Aucun risque.** `--renormalize` ne change que les fins de ligne, jamais le contenu. Python, YAML et JavaScript acceptent les deux formats indifféremment.

---

## Partie E — Vérifier et commiter

### E.1 — Tout compile

```powershell
python -m compileall app api auth events kpi metrics realtime reports seed simulation run_simulation.py
```

### E.2 — L'API démarre et le temps réel fonctionne

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Vérifie <http://127.0.0.1:8000/health>, puis le dashboard et **le badge `connecté`** (partie C).

### E.3 — Le Dockerfile porte le bon nom

```powershell
git ls-files | Select-String -Pattern "Dockerfile"
```

Attendu : `Dockerfile` et `dashboard/Dockerfile`. **Aucun `dockerfile` en minuscule.**

### E.4 — Commit

⚠️ **Depuis la racine du projet**, pas depuis `dashboard/`. Vérifie ton invite.

```powershell
cd C:\Users\charles.nguessan\Documents\simulateur_V5
```

```powershell
git add .
```

```powershell
git status --short
```

```powershell
git commit -m "docker: renomme Dockerfile, corrige la copie des migrations, ouvre le CORS Socket.IO"
```

```powershell
git push origin main
```

### E.5 — Contrôler la CI

Va sur <https://github.com/charlesemm/simulateur_V5/actions>.

Le workflow **CI — Tests & Build** doit se lancer. Surveille le job **`Docker — build des images`** : c'est celui qui échouait à cause de la casse du Dockerfile. Il doit désormais passer au vert.

---

## Récapitulatif

| Partie | Fichier | Modification | Effet |
|---|---|---|---|
| **R.1** | `api/__init__.py` | Restaurer la docstring d'origine | Reste du chantier 2 |
| **R.2** | `api/routers/__init__.py` | Retirer l'import `HealthResponse` | Reste du chantier 2 |
| **A** | `dockerfile` → `Dockerfile` | Renommer via `git mv` en deux temps | 🔧 Débloque la CI |
| **B** | `Dockerfile` ligne 18 | `COPY` en deux instructions | 🔧 Débloque la production |
| **C** | `realtime/socket_server.py` | `cors_allowed_origins=_cors_origins` | 🎯 **Badge `connecté`** |
| **D** | `.gitattributes` | **Créer** + `git add --renormalize .` | 🧹 Diffs lisibles |

---

## Ce qu'on ne fait PAS dans ce chantier

**Le proxy Nginx** de `dashboard/nginx.conf` (lignes 18-36) est commenté. Il permettrait de servir le dashboard et l'API sur **un seul domaine**, supprimant toute question de CORS en production.

C'est une **décision d'architecture de déploiement**, pas une réparation. Elle dépend de l'endroit où le projet sera hébergé. À traiter le jour où le déploiement sera décidé.

---

## Suite du plan

| Chantier | Objet |
|---|---|
| ~~0~~ | ~~Remise en route sur la nouvelle machine~~ ✅ |
| ~~1~~ | ~~Hygiène git & secrets~~ ✅ commit `fad04bd` |
| ~~2~~ | ~~Nettoyage des doublons~~ ✅ commit `7ef5a3c` |
| **3** | **Docker & temps réel** ← *ce guide* |
| 4 | Sécuriser les endpoints non protégés |
| 5 | Brancher les anomalies sur le moteur (ou corriger la doc) |
| 6 | Performance des KPI (agrégations SQL) |
| 7 | Tests automatisés (pytest + CI) |
| 8 | Figer la migration `0001` en SQL explicite |
