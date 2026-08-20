# GUIDE 2 — Nettoyage des doublons et du code mort

> **Chantier 2 sur 8** du plan de remise en ordre du projet `simulateur_V5`.
> Prérequis : [GUIDE_1_HYGIENE_GIT_SECRETS.md](./GUIDE_1_HYGIENE_GIT_SECRETS.md) terminé (commit `fad04bd` poussé).

---

## En deux mots

Ce chantier ne corrige **aucun bug visible**. Il enlève du code qui ne sert à rien : une fonction écrite deux fois, six imports inutilisés, et un fichier en double déjà disparu.

**C'est le chantier le moins risqué du plan.** On ne touche à aucune logique métier. Si tu te trompes, Python te le dira immédiatement au démarrage.

**Pourquoi le faire :** du code mort, c'est du code qu'on lit, qu'on croit utile, et qui égare. Le `run()` écrit deux fois dans `run_simulation.py` en est l'exemple parfait — un lecteur perd du temps à comprendre laquelle des deux versions s'exécute.

---

## Table des matières

- [Ce qui est déjà fait](#ce-qui-est-déjà-fait)
- [Partie A — La fonction `run()` écrite deux fois](#partie-a--la-fonction-run-écrite-deux-fois)
- [Partie B — Les six imports inutilisés](#partie-b--les-six-imports-inutilisés)
- [Partie C — Le mot de passe affiché en clair](#partie-c--le-mot-de-passe-affiché-en-clair)
- [Partie D — Optionnel : charger le `.env` automatiquement](#partie-d--optionnel--charger-le-env-automatiquement)
- [Partie E — Vérifier et commiter](#partie-e--vérifier-et-commiter)
- [Récapitulatif](#récapitulatif)

---

## Ce qui est déjà fait

Deux points prévus au chantier 2 sont **déjà réglés** :

| Élément | État | Comment |
|---|---|---|
| `docker-compse.yml` (faute de frappe, doublon de `docker-compose.yml`) | ✅ **Supprimé** | Absent du disque |
| `reports/output/*.xlsx` et `*.pdf` (artefacts générés) | ✅ **Retirés du suivi git** | Par le `.gitignore` du chantier 1 |

Il reste donc **trois corrections**, plus une option.

---

## Partie A — La fonction `run()` écrite deux fois

**Fichier :** `run_simulation.py`

### Le problème

Le fichier définit `async def run()` **deux fois** : ligne 24 et ligne 35. Les deux corps sont identiques, à une ligne vide près.

En Python, la **seconde définition écrase silencieusement la première**. Le programme fonctionne — mais 10 lignes sur 47 sont mortes, et un lecteur ne peut pas savoir laquelle compte sans y réfléchir.

### La correction

Remplace **tout le contenu** de `run_simulation.py` par ceci :

```python
"""Lance le moteur CMU en standalone depuis la ligne de commande."""

import argparse
import asyncio
import logging
from simulation import SimulationEngine, SimulationEvent

async def log_event(event: SimulationEvent) -> None:
    """Affiche chaque événement en attendant Socket.IO à l'étape 4."""

    logging.getLogger("evenements").info("%s | %s", event.event_type, event.to_dict())

def parse_arguments() -> argparse.Namespace:
    """Valide les paramètres de lancement standalone."""

    parser = argparse.ArgumentParser(description="Simulateur standalone du parcours assuré CMU.")
    parser.add_argument("--nombre-passages", type=int, default=10)
    parser.add_argument("--vitesse", type=float, default=60.0)
    arguments = parser.parse_args()
    if arguments.nombre_passages <= 0 or arguments.vitesse <= 0:
        parser.error("Les deux paramètres doivent être strictement positifs.")
    return arguments

async def run() -> None:
    """Configure et attend la fin du moteur."""

    arguments = parse_arguments()
    engine = SimulationEngine(event_callback=log_event)
    engine.set_speed(arguments.vitesse)
    try:
        await engine.start(arguments.nombre_passages)
    except KeyboardInterrupt:
        await engine.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    asyncio.run(run())
```

**Ce qui change :** les lignes 35 à 43 (la seconde définition de `run()`) disparaissent. Le fichier passe de 47 à 37 lignes. **Rien d'autre n'est modifié.**

### Vérifier

```powershell
python -c "import ast, io; a = ast.parse(io.open('run_simulation.py', encoding='utf-8').read()); print('definitions de run() :', sum(1 for n in a.body if getattr(n, 'name', None) == 'run'))"
```

Attendu : `definitions de run() : 1`

---

## Partie B — Les six imports inutilisés

Un import inutilisé fait croire qu'un module est employé alors qu'il ne l'est pas. Chacun des six ci-dessous n'apparaît **qu'une seule fois** dans son fichier : sur sa propre ligne d'import.

> ⚠️ **Ne touche pas aux lignes `from __future__ import annotations`.** Ce n'est pas un import mais une **directive du compilateur** : elle change la façon dont Python traite les annotations de type. Elle paraît inutilisée à un outil d'analyse, mais la supprimer casse le fichier.

### B.1 — `api/schema.py` ligne 6

**Supprime cette ligne :**

```python
from typing import Any
```

### B.2 — `metrics/registry.py` ligne 10

**Supprime cette ligne :**

```python
import os
```

> Le module `ctypes` juste au-dessus, lui, **est bien utilisé** — c'est lui qui lit la mémoire du processus via l'API Win32. Ne le touche pas.

### B.3 — `simulation/events.py` ligne 5

**Remplace :**

```python
from datetime import datetime, timezone
```

**Par :**

```python
from datetime import datetime
```

### B.4 — `simulation/passage.py` ligne 15

**Remplace :**

```python
    Agent, HealthCenter, HealthProfessional, InsuredPerson, Invoice,
```

**Par :**

```python
    Agent, HealthCenter, HealthProfessional, Invoice,
```

> `InsuredPerson` n'est pas utilisé ici : le passage reçoit un `insured_id` (un UUID) et ne manipule jamais l'objet complet.

### B.5 — `api/routers/__init__.py` ligne 4

**Supprime cette ligne :**

```python
from api.schema import HealthResponse
```

Le fichier doit alors ressembler à :

```python
"""Regroupe les routers HTTP du simulateur."""

from api.routers import centres, factures, kpi, simulation

__all__ = ["centres", "factures", "kpi", "simulation"]
```

> `HealthResponse` n'est pas dans `__all__` : ce n'est donc même pas une ré-export volontaire, juste un reliquat. Le vrai usage est dans `api/main.py`, qui l'importe directement depuis `api.schema`.

### B.6 — `auth/bootstrap.py` ligne 8

⚠️ **Celui-ci, ne le supprime pas.** Traite-le en [partie C](#partie-c--le-mot-de-passe-affiché-en-clair) — on va justement s'en servir.

---

## Partie C — Le mot de passe affiché en clair

**Fichier :** `auth/bootstrap.py`

### Le problème

Le script importe `getpass` ligne 8… puis ne l'utilise jamais. Ligne 41, il lit le mot de passe avec `input()` :

```python
    mot_de_passe = input("Mot de passe (8 caractères minimum) : ")
```

**Conséquence :** le mot de passe administrateur s'affiche **en clair à l'écran** pendant la frappe, et reste visible dans l'historique du terminal.

L'intention d'origine était visiblement d'utiliser `getpass` — l'import est là, l'appel manque. C'est un oubli, pas un choix.

### La correction

**Remplace la ligne 41 :**

```python
    mot_de_passe = input("Mot de passe (8 caractères minimum) : ")
```

**Par :**

```python
    mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
```

**Un seul mot change**, et l'import de la ligne 8 devient enfin utile.

> **Comportement de `getpass` :** rien ne s'affiche pendant la frappe — pas même des astérisques. C'est normal, tape à l'aveugle et valide avec Entrée.

### Vérifier

```powershell
python -m auth.bootstrap
```

Entre un email quelconque, un nom, puis un mot de passe : **il ne doit rien s'afficher** pendant que tu tapes.

Si le compte est créé alors que tu ne le voulais pas, supprime-le :

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "DELETE FROM \"TB_UTILISATEURS\" WHERE \"EMAIL\" = 'email_de_test';"
```

---

## Partie D — Optionnel : charger le `.env` automatiquement

> 🟡 **Cette partie est facultative.** Elle change un comportement, contrairement aux parties A à C. Décide si tu la veux.

### Le problème

Aux chantiers 0 et 1, tu as été bloqué **trois fois** par la même cause : `DATABASE_URL` ou `JWT_SECRET_KEY` absentes du terminal. À chaque nouvelle fenêtre PowerShell, il faut retaper :

```powershell
$env:DATABASE_URL = "..."
$env:JWT_SECRET_KEY = "..."
```

Or le projet a `python-dotenv` **installé** — et ne l'appelle **jamais**. Le `.env` ne sert aujourd'hui qu'à Docker.

### La correction

**Fichier :** `app/database.py` — ajoute ces deux lignes **au tout début**, avant les autres imports :

```python
from dotenv import load_dotenv

load_dotenv()
```

Le haut du fichier devient :

```python
"""Configure le moteur SQLAlchemy asynchrone et les sessions PostgreSQL."""

import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Charge le fichier .env local s'il existe. Les variables déjà définies dans
# l'environnement gardent la priorité : Docker et la CI ne sont pas affectés.
load_dotenv()
```

**Fichier :** `auth/security.py` — même ajout, car ce module peut être importé sans passer par `app.database` :

```python
from dotenv import load_dotenv

load_dotenv()
```

### Ce que ça change

| Avant | Après |
|---|---|
| Retaper 2 variables à chaque terminal | Le `.env` est lu automatiquement |
| Rituel de démarrage : 4 commandes | Rituel : `uvicorn api.main:app --reload` |

> 🔒 **Aucun risque de sécurité.** `load_dotenv()` **n'écrase jamais** une variable déjà présente dans l'environnement. En Docker et en CI, où les variables sont injectées, le `.env` est simplement ignoré. Et le fichier reste hors de git.

### Ajouter la dépendance

`python-dotenv` est installé dans ton `.venv` mais **absent de `requirements.txt`** — il y est arrivé comme dépendance indirecte. Si tu appliques cette partie, ajoute-le explicitement à la fin de `requirements.txt` :

```
# Chargement du fichier .env en développement local.
python-dotenv>=1.0.0
```

Sinon un collègue qui réinstalle depuis `requirements.txt` obtiendra un `ModuleNotFoundError`.

---

## Partie E — Vérifier et commiter

### E.1 — Tout compile

```powershell
python -m compileall app api auth events kpi metrics realtime reports seed simulation run_simulation.py
```

Aucune erreur attendue. C'est exactement la commande que lance la CI GitHub Actions.

### E.2 — Les modules s'importent

```powershell
python -c "import app.database, auth.security, api.main, simulation.passage, simulation.events, api.schema, metrics.registry, api.routers; print('Tous les modules OK')"
```

Attendu : `Tous les modules OK`

> C'est ici qu'un import supprimé à tort se manifesterait, par un `NameError` ou un `ImportError` explicite.

### E.3 — L'API démarre

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Vérifie <http://127.0.0.1:8000/health>, puis `Ctrl+C`.

### E.4 — Commit

```powershell
git add .
```

```powershell
git status --short
```

```powershell
git commit -m "nettoyage: supprime le run() duplique, les imports morts et masque la saisie du mot de passe"
```

```powershell
git push origin main
```

---

## Récapitulatif

| Partie | Fichier | Modification | Risque |
|---|---|---|---|
| **A** | `run_simulation.py` | Supprime la 2e définition de `run()` (lignes 35-43) | 🟢 nul |
| **B.1** | `api/schema.py` | Supprime `from typing import Any` (ligne 6) | 🟢 nul |
| **B.2** | `metrics/registry.py` | Supprime `import os` (ligne 10) | 🟢 nul |
| **B.3** | `simulation/events.py` | Retire `timezone` de l'import (ligne 5) | 🟢 nul |
| **B.4** | `simulation/passage.py` | Retire `InsuredPerson` de l'import (ligne 15) | 🟢 nul |
| **B.5** | `api/routers/__init__.py` | Supprime l'import de `HealthResponse` (ligne 4) | 🟢 nul |
| **C** | `auth/bootstrap.py` | `input()` → `getpass.getpass()` (ligne 41) | 🟢 nul |
| **D** | `app/database.py`, `auth/security.py`, `requirements.txt` | *Optionnel* — charge le `.env` automatiquement | 🟡 change un comportement |

**Bilan :** environ 10 lignes de code mort supprimées, un défaut de sécurité mineur corrigé, et si tu prends la partie D, plus jamais de `RuntimeError: la variable est obligatoire`.

---

## Suite du plan

| Chantier | Objet |
|---|---|
| ~~0~~ | ~~Remise en route sur la nouvelle machine~~ ✅ |
| ~~1~~ | ~~Hygiène git & secrets~~ ✅ commit `fad04bd` |
| **2** | **Nettoyage des doublons** ← *ce guide* |
| 3 | Réparer Docker (`Dockerfile`, `COPY alembic/`, **CORS Socket.IO**) |
| 4 | Sécuriser les endpoints non protégés |
| 5 | Brancher les anomalies sur le moteur (ou corriger la doc) |
| 6 | Performance des KPI (agrégations SQL) |
| 7 | Tests automatisés (pytest + CI) |
| 8 | Figer la migration `0001` en SQL explicite |

> 💡 Le chantier 3 réglera le **badge temps réel déconnecté** que tu vois depuis le chantier 0.
