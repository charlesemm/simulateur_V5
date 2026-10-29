# Guide du développeur

## Prérequis

- Python **3.14** (comme l'image), Node 22, PostgreSQL 16 (local ou via Podman).
- Windows/PowerShell ou Linux. Les commandes ci-dessous sont en PowerShell.

## Installer

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt        # ou, à l'identique de la CI : pip install --require-hashes -r requirements-dev.lock
$env:PYTHONPATH = "src"                    # le code vit sous src/echo/
copy .env.exemple .env                     # puis renseigner DATABASE_URL et JWT_SECRET_KEY
python -m alembic upgrade head
$env:ECHO_ADMIN_PASSWORD = "..."
python -m echo.web.auth.bootstrap --creer --email admin@exemple.ci --utilisateur admin --nom "Administrateur"
                                           # (sans --creer : mode interactif)
python -m echo.moteur.seed                 # référentiels et données de départ
uvicorn echo.web.api.main:app --reload --port 8000
```

Le point d'entrée ASGI est `echo.web.api.main:app` (Socket.IO enveloppant FastAPI).

## Tests

```powershell
python -m pytest                 # toute la suite
python -m pytest tests/test_api.py -k facture
```

- Configuration : `pytest.ini` (`pythonpath = src`, `asyncio_mode = auto`, une boucle d'événements pour la session).
- **Base de test séparée** : nom de la base de travail + suffixe `_test`. La suite **tronque les tables** entre les cas et refuse de démarrer si la base de test coïncide avec la base de travail.
- Marqueur `base` : test qui exige PostgreSQL.

Couverture par thème : API et sécurité (`test_api`, `test_securite`, `test_cors`, `test_sonde_login`, `test_creation_comptes`, `test_bootstrap_comptes`), moteur (`test_parcours_moteur`, `test_moteur_contre_pression`, `test_socle_aleas`, `test_simulation_inscription`, `test_executions`), anomalies (`test_anomalies*`, `test_refus_et_parcours`), campagnes et témoin (`test_campagnes`, `test_echange`, `test_temoin`), qualité et gouvernance (`test_qualite`, `test_provenance_et_panorama`, `test_moteurs`), référentiels (`test_referentiels_cnam`, `test_tarifs_actes`, `test_identifiants`), temps réel (`test_kpi`), image (`test_image`), dette technique (`test_dette_technique`).

## Scripts utilitaires (`tools/`)

| Script | Usage |
|---|---|
| `verifier_temps_reel.py` | Lance l'ASGI, connecte un client Socket.IO et exige les événements KPI |
| `verifier_seeds.py` | Contrôle les données de départ |
| `verifier_attributs_modeles.py` | Cohérence modèles ORM / schéma |
| `extraire_schema_mirka.py`, `generer_modeles_orm.py`, `generer_tables_sim.py` | Régénèrent le code dérivé du schéma Mirka |

## Ajouter une fonctionnalité

**Un nouvel endpoint** — créer ou compléter un routeur dans `src/echo/web/api/routers/`, y poser `require_role(...)`, l'inclure dans `web/api/main.py`, ajouter un test dans `tests/`.

**Une nouvelle table** — modèle SQLAlchemy dans le module métier concerné, puis `python -m alembic revision -m "..."`. Les tables `TB_SIM_*` viennent de `schema_mirka/` : modifier la source et régénérer.

**Un nouveau type d'anomalie** — ajouter le code **en fin** de `catalogue.py` (l'ordre fixe les tirages), une migration qui peuple `TB_REF_ANOMALIES`, la logique d'injection, et vérifier sa portée (`toutes` ou `campagne`).

**Un nouvel aléa** — constante et réglages dans `moteur/simulation/aleas.py`, effet dans `passage.py`, événement `alea.*` publié sur le bus.

**Un nouvel écran** — ajouter l'onglet dans `dashboard/src/navigation.ts`, le composant dans `components/`, le branchement dans `App.tsx` et `Sidebar.tsx`.

## Conventions du code

- Noms, commentaires et messages **en français** ; les commentaires expliquent le *pourquoi* (un piège évité, une décision), pas le *comment*.
- Reproductibilité : tout tirage aléatoire passe par un générateur ensemencé.
- Ce qu'on affiche à l'écran doit fonctionner : pas d'interrupteur sans effet.
- Pas de valeur de configuration en dur côté navigateur quand le serveur peut la dire (cf. `disponible`, `parcours`).
- Les dépendances Python sont **verrouillées** : après toute modification de `requirements*.txt`, régénérer `requirements.lock` et `requirements-dev.lock` dans un conteneur (commande en tête de `requirements.txt`).

## CI/CD

`.github/workflows/ci.yml` — détail dans [GUIDE_CICD.md](GUIDE_CICD.md).

| Job | Étapes |
|---|---|
| Backend | installation verrouillée, `compileall src`, migrations sur base vierge, création de la base de test, `pytest`, `bandit`, `pip-audit`, smoke test `/health` |
| Frontend | lint, `tsc` + build |
| Livraison | construction et publication de l'image sur GHCR (`main` et tags `v*`, seulement si le reste est vert) |

Le pipeline s'arrête à l'image : le déploiement sur le serveur reste manuel ([GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md), [GUIDE_EXPLOITATION.md](GUIDE_EXPLOITATION.md)).

## Conteneurs

```powershell
podman machine start
podman compose up -d        # postgres, migrations (une fois), api (+ dashboard compilé)
podman compose ps
curl http://localhost:8000/health
```

Le `Containerfile` est en trois étages : build du dashboard (Node 22), dépendances Python verrouillées, image finale non-root. Le service `migrations` applique Alembic avant le démarrage de l'API. Voir [GUIDE_PODMAN.md](GUIDE_PODMAN.md).

## Postman

`postman/` contient une collection (`TEST SIMULATION`) et l'environnement `echo_prod`. Les secrets ne vont pas dans le dépôt : utiliser des variables d'environnement Postman.
