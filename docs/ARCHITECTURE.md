# Architecture

## Vue d'ensemble

```text
  Navigateur (dashboard React 19)
        │  REST (JWT)               │  Socket.IO /kpi (JWT)
        ▼                           ▼
  ┌──────────────────────────────────────────────┐
  │ ASGI : socketio.ASGIApp                      │
  │   ├─ /socket.io  → serveur Socket.IO         │
  │   └─ le reste    → FastAPI (echo.web.api)    │
  └───────┬───────────────────────────┬──────────┘
          │ routeurs                  │ lifespan
          ▼                           ▼
   echo.metier.*  ◄── echo.moteur ──► bus d'événements ──► consommateurs
   (règles métier)    (simulation)    (asyncio)             KPI, parcours
          │                │                                    │
          └────────► PostgreSQL 16 (SQLAlchemy async) ◄─────────┘
```

Un seul processus (un seul worker uvicorn) porte l'API REST, le temps réel, le moteur de simulation et le planificateur de rapports. Ce choix est assumé : le limiteur de connexions et plusieurs compteurs vivent en mémoire (voir [CONFIGURATION_ET_SECURITE.md](CONFIGURATION_ET_SECURITE.md)).

## Arborescence

Tout le code Python vit sous `src/echo/` (le `PYTHONPATH` doit pointer sur `src`).

```text
src/echo/
├── moteur/                  ← le simulateur
│   ├── simulation/          ← moteur de passages, aléas, profils, commandes, purge
│   │   └── schema_sim/      ← tables de faits et tables générées du schéma Mirka
│   ├── events/              ← bus d'événements interne + journal TB_EVENEMENTS_METIER
│   ├── realtime/            ← serveur Socket.IO, consommateurs KPI et parcours
│   ├── seed/                ← alimentation des référentiels et données de départ
│   ├── run_simulation.py    ← lancement du moteur hors API
│   └── simulation_config.py ← configuration du moteur (vitesse, concurrence)
├── metier/                  ← règles métier, par domaine
│   ├── anomalies/           ← catalogue, configuration, journal d'injections
│   ├── campagnes/           ← campagnes de test qualité (génération, export, échange)
│   ├── qualite/             ← règles et rapport de contrôle qualité
│   ├── temoin/              ← outil témoin de référence
│   ├── mdm/                 ← rapprochement d'identités (vérité terrain, évaluation)
│   ├── entrepot/            ← génération d'historique pour l'entrepôt
│   ├── gouvernance/         ← catalogue, inventaire, volumétrie, panorama, provenance
│   └── kpi/                 ← calcul des indicateurs et consommateur d'événements
└── web/                     ← exposition HTTP
    ├── api/                 ← main.py (assemblage), routers/, services/, schema.py
    ├── app/                 ← base de données, CORS, modèles ORM (dont Mirka)
    ├── auth/                ← JWT, bcrypt, rôles, limitation, bootstrap admin
    ├── metrics/             ← registre de métriques techniques
    └── reports/             ← générateurs PDF, Excel, CSV et planificateur
```

Autres dossiers à la racine :

| Dossier / fichier | Contenu |
|---|---|
| `dashboard/` | Application React (Vite, TypeScript, Recharts) |
| `alembic/` | Migrations ; `versions/` = socle actuel, `versions_archive/` = anciennes migrations |
| `schema_mirka/` | Sources du schéma de référence (`ossature.sql`, `schema_sim.json`, classeurs Excel) |
| `tools/` | Scripts de génération et de vérification (ORM, tables, seeds, temps réel) |
| `tests/` | Suite pytest |
| `deploiement/` | Compose de production, Caddy, vhost nginx, sauvegarde |
| `postman/` | Collection et environnement Postman |
| `Containerfile`, `compose.yaml` | Image et orchestration locale |
| `.github/workflows/ci.yml` | Pipeline CI/CD |

## Cycle de vie de l'application

Au démarrage (`lifespan` dans `web/api/main.py`) :

1. chargement de la configuration d'anomalies depuis la base ;
2. chargement du catalogue d'anomalies (`TB_REF_ANOMALIES`) ;
3. démarrage des consommateurs d'événements (KPI et parcours) ;
4. démarrage du planificateur de rapports (APScheduler).

À l'arrêt : arrêt du planificateur, arrêt de la simulation en cours, arrêt des consommateurs, puis sauvegarde du compteur d'anomalies injectées (un échec de sauvegarde est journalisé mais n'empêche pas l'arrêt).

## Flux de données d'une simulation

1. Un opérateur appelle `POST /simulation/start` (profil, vitesse, anomalies).
2. `simulation_manager` démarre le `SimulationEngine`, qui lance des **passages** concurrents, bornés par un `asyncio.Semaphore`.
3. Chaque passage écrit en base (assuré, facture, prestations, prescriptions, ententes) et **publie des événements** sur le bus (`facture.creee`, `prestation.servie`, `passage.refuse`, `alea.*`…).
4. Le **consommateur KPI** agrège les événements et diffuse `kpi:snapshot` / mises à jour sur le namespace Socket.IO `/kpi`. Le **consommateur de parcours** diffuse le fil de chaque passage.
5. Le dashboard affiche le tout en direct ; l'historique des exécutions reste consultable via `/simulation/executions`.

## Authentification et rôles

JWT signé avec `JWT_SECRET_KEY` (obligatoire, l'API refuse de démarrer sans). Trois rôles hiérarchiques : `observateur` < `operateur` < `administrateur`. Un rôle donne accès à son niveau et aux niveaux inférieurs (`require_role`). Détail dans [CONFIGURATION_ET_SECURITE.md](CONFIGURATION_ET_SECURITE.md).

## Servir le dashboard

Si `dashboard/dist` existe (cas de l'image conteneur), FastAPI sert l'interface sur `/`, ses fichiers sur `/assets`, et renvoie `index.html` pour toute route inconnue de l'API (application mono-page). Les chemins remontants sont refusés. En développement, Vite sert l'interface sur le port 5173.
