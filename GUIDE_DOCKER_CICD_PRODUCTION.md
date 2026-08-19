# Guide complet — Docker, CI/CD GitHub Actions & Déploiement Production

## ⚠️ Important avant de commencer

**Ce guide met en place l'infrastructure complète pour passer du développement local à la production sur les serveurs de la boîte.**

À chaque étape, tu trouveras :
- **Exactement** ce qu'il faut faire
- **Où** le faire (fichier + rôle)
- Le **code complet** à copier-coller
- Les **commandes** de vérification

Ce guide s'appuie sur l'analyse du code actuel du simulateur CMU :
- **Backend** : FastAPI + Socket.IO (`api.main:app`), Uvicorn, Alembic, seed Python
- **Frontend** : React 19 + Vite (`dashboard/`)
- **Base** : PostgreSQL 16 (asyncpg)
- **Auth** : JWT + bcrypt, rôles administrateur / opérateur / observateur

---

## 📋 Vue d'ensemble

### Le flux complet (dev → prod)

```text
┌──────────────┐   git push    ┌─────────────┐   CI auto     ┌──────────────┐
│  Ton PC      │ ────────────► │   GitHub    │ ────────────► │ Tests + Build│
│ docker compose│              │   (repo)    │               │   image Docker│
└──────────────┘               └──────┬──────┘               └──────┬───────┘
                                      │                             │
                               Pull Request                    ✅ merge main
                                      │                             │
                                      ▼                             ▼
                               Revue de code              GitHub Actions (CD)
                                                            Push image → Serveur boîte
                                                                      │
                                                                      ▼
                                                            docker compose up (prod)
                                                            alembic upgrade head
```

### Fichiers à créer et modifier

```text
Fichiers À CRÉER :
├── Dockerfile                          ← Image backend (API + simulateur)
├── .dockerignore                       ← Exclure venv, cache, secrets du build
├── docker-compose.yml                  ← Environnement DEV (hot reload)
├── docker-compose.prod.yml             ← Environnement PROD (images figées)
├── .env.example                        ← Modèle de variables (sans secrets)
├── scripts/docker-entrypoint.sh        ← Attendre Postgres + migrations au démarrage
├── dashboard/Dockerfile                ← Build React + Nginx (prod)
├── dashboard/nginx.conf                ← Servir le SPA + proxy API (option prod)
├── dashboard/.dockerignore
├── .github/workflows/ci.yml            ← Tests automatiques à chaque push/PR
└── .github/workflows/deploy.yml        ← Déploiement auto sur merge main

Fichiers À MODIFIER :
├── api/main.py                         ← CORS configurable par variable d'environnement
├── dashboard/vite.config.ts            ← Host 0.0.0.0 pour Docker dev
└── README.md                           ← Lien vers ce guide (optionnel)
```

### Architecture Docker (3 services)

| Service     | Rôle                                      | Port dev | Port prod |
|-------------|-------------------------------------------|----------|-----------|
| `db`        | PostgreSQL 16, volume persistant          | 5432     | interne   |
| `api`       | Uvicorn `api.main:app` (FastAPI+Socket.IO)  | 8000     | 8000      |
| `dashboard` | Vite dev (dev) / Nginx static (prod)      | 5173     | 80        |

---

## 1. Prérequis

### Sur ton PC (développement)

| Outil            | Version min. | Vérification              |
|------------------|--------------|---------------------------|
| Docker Desktop   | 4.x          | `docker --version`        |
| Docker Compose   | v2           | `docker compose version`  |
| Git              | 2.x          | `git --version`           |
| Compte GitHub    | —            | Repo du projet créé       |

### Sur le serveur de production (au choix)

#### Option 1 : Serveur d'entreprise / dédié (interne ou VPS)
| Élément                    | Détail                                              |
|----------------------------|-----------------------------------------------------|
| OS                         | Linux (Ubuntu 22.04+ recommandé)                    |
| Docker + Compose           | Installés par l'admin système                         |
| Accès réseau               | SSH depuis GitHub Actions **ou** runner self-hosted |
| Registre d'images          | GitHub Container Registry (`ghcr.io`) ou registre interne |
| Nom de domaine (optionnel) | ex. `cmu-simulateur.entreprise.ci`                  |
| PostgreSQL                 | Conteneur Docker **ou** instance managée interne    |

#### Option 2 : 100% Gratuit (Sans aucun serveur payant)
| Composant                  | Fournisseur gratuit recommandé                       | Coût |
|----------------------------|-----------------------------------------------------|------|
| Base PostgreSQL            | **Neon.tech** ou **Supabase**                       | 0 €  |
| Backend API & WebSockets   | **Koyeb** ou **Render**                             | 0 €  |
| Frontend React Vite        | **Vercel** ou **Cloudflare Pages**                  | 0 €  |
| Nom de Domaine & SSL HTTPS | Inclus (`*.vercel.app`, `*.koyeb.app`) ou **DuckDNS** | 0 €  |
| Alternative VPS tout-en-un | **Oracle Cloud Always Free** (4 OCPU ARM, 24 Go RAM)| 0 €  |


### Stratégie de branches Git (recommandée)

```text
main        → code stable, déployé en PRODUCTION
develop     → intégration des features, déployé en STAGING (optionnel)
feature/xxx → ton travail quotidien
```

**Règle** : jamais de push direct sur `main` sans Pull Request + CI verte.

---

## **ÉTAPE 1 : Créer `.dockerignore`**

Empêche Docker de copier le venv, les caches et les secrets dans l'image.

**Fichier entièrement nouveau** à la racine du projet :

```dockerignore
# Environnements Python locaux
.venv/
venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/

# Secrets — JAMAIS dans l'image
.env
.env.*
!.env.example

# IDE et git
.idea/
.git/
.gitignore

# Frontend — build séparé dans dashboard/Dockerfile
dashboard/node_modules/
dashboard/dist/

# Rapports générés localement
reports/output/*.pdf
reports/output/*.xlsx

# Documentation et guides (inutiles en prod)
*.md
!README.md

# Fichiers temporaires OS
.DS_Store
Thumbs.db
```

**✅ Action :** crée `.dockerignore` à la racine, copie le contenu, sauvegarde.

---

## **ÉTAPE 2 : Créer `Dockerfile` (backend API)**

Image Python pour l'API FastAPI, le moteur de simulation, Alembic et le seed.

**Fichier entièrement nouveau** à la racine :

```dockerfile
# ── Simulateur CMU — image backend ──────────────────────────────────────────
FROM python:3.12-slim AS base

# psycopg2/asyncpg et alembic ont parfois besoin de libs système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances Python en couche séparée (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY alembic.ini alembic/ ./
COPY app/ app/
COPY api/ api/
COPY auth/ auth/
COPY events/ events/
COPY kpi/ kpi/
COPY metrics/ metrics/
COPY realtime/ realtime/
COPY reports/ reports/
COPY seed/ seed/
COPY simulation/ simulation/
COPY simulation_config.py run_simulation.py ./

# Répertoire des rapports générés (volume monté en prod)
RUN mkdir -p reports/output

# Script d'entrée : attend Postgres, lance les migrations
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Utilisateur non-root (bonne pratique sécurité)
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]

# Point d'entrée ASGI : api.main:app inclut Socket.IO
# En prod : pas de --reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Points clés :**
- Le point d'entrée est `api.main:app` (wrapper Socket.IO), **pas** `fastapi_app`.
- `--reload` est **absent** en prod ; il sera ajouté uniquement dans `docker-compose.yml` (dev).

**✅ Action :** crée `Dockerfile` à la racine.

---

## **ÉTAPE 3 : Créer `scripts/docker-entrypoint.sh`**

Ce script attend que PostgreSQL soit prêt, applique les migrations Alembic, puis démarre Uvicorn.

**Crée d'abord le dossier** `scripts/` s'il n'existe pas.

```bash
#!/usr/bin/env bash
# Attend PostgreSQL, applique Alembic, puis exécute la commande passée (uvicorn).
set -euo pipefail

echo "⏳ Attente de PostgreSQL (${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432})..."

until python -c "
import asyncio, os, sys
import asyncpg

async def check():
    url = os.environ.get('DATABASE_URL', '')
    # Extraire host/port/user/password/db depuis DATABASE_URL asyncpg
    # Format : postgresql+asyncpg://user:pass@host:port/dbname
    dsn = url.replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn)
    await conn.close()

try:
    asyncio.run(check())
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  sleep 2
done

echo "✅ PostgreSQL disponible."

echo "🔄 Application des migrations Alembic..."
python -m alembic upgrade head
echo "✅ Migrations appliquées."

# Seed automatique UNIQUEMENT si SEED_ON_START=true (premier déploiement)
if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "🌱 Exécution du seed référentiel..."
  python -m seed
  echo "✅ Seed terminé."
fi

echo "🚀 Démarrage de l'application..."
exec "$@"
```

**✅ Action :**
1. Crée `scripts/docker-entrypoint.sh`
2. Copie le contenu
3. Rend le script exécutable (Git le conservera ; sous Linux/Mac : `chmod +x scripts/docker-entrypoint.sh`)

---

## **ÉTAPE 4 : Créer `docker-compose.yml` (développement)**

En dev, ton code local est **monté en volume** : les modifications Python/React sont visibles sans rebuild.

```yaml
# docker-compose.yml — Environnement de DÉVELOPPEMENT
# Usage : docker compose up --build

services:

  db:
    image: postgres:16-alpine
    container_name: cmu_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme_dev}
      POSTGRES_DB: ${POSTGRES_DB:-cmu_simulator}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-cmu_simulator}"]
      interval: 5s
      timeout: 5s
      retries: 10

  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: cmu_api
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-changeme_dev}@db:5432/${POSTGRES_DB:-cmu_simulator}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-dev-secret-change-me-en-production}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:5173,http://127.0.0.1:5173}
      ANOMALIES_ENABLED: ${ANOMALIES_ENABLED:-false}
      ANOMALIES_RATE: ${ANOMALIES_RATE:-0.0}
      SEED_ON_START: ${SEED_ON_START:-false}
    ports:
      - "8000:8000"
    volumes:
      # Hot reload : ton code local → conteneur
      - ./api:/app/api
      - ./app:/app/app
      - ./auth:/app/auth
      - ./events:/app/events
      - ./kpi:/app/kpi
      - ./metrics:/app/metrics
      - ./realtime:/app/realtime
      - ./reports:/app/reports
      - ./seed:/app/seed
      - ./simulation:/app/simulation
      - ./simulation_config.py:/app/simulation_config.py
      - ./alembic:/app/alembic
      - reports_output:/app/reports/output
    command: >
      uvicorn api.main:app
      --host 0.0.0.0
      --port 8000
      --reload

  dashboard:
    image: node:22-alpine
    container_name: cmu_dashboard
    working_dir: /app
    restart: unless-stopped
    depends_on:
      - api
    environment:
      VITE_API_URL: ${VITE_API_URL:-http://127.0.0.1:8000}
    ports:
      - "5173:5173"
    volumes:
      - ./dashboard:/app
      - dashboard_node_modules:/app/node_modules
    command: sh -c "npm install && npm run dev -- --host 0.0.0.0 --port 5173"

volumes:
  postgres_data:
  reports_output:
  dashboard_node_modules:
```

**Ce que ça change par rapport à aujourd'hui :**

| Avant (sans Docker)                    | Après (docker compose up)                    |
|----------------------------------------|----------------------------------------------|
| PostgreSQL installé localement         | Conteneur `db`, données dans volume Docker   |
| `uvicorn ... --reload` manuel          | Service `api` avec reload automatique        |
| `npm run dev` dans un 2e terminal      | Service `dashboard` inclus                     |
| `DATABASE_URL=...@localhost:5432`      | `DATABASE_URL=...@db:5432` (nom du service)  |

**✅ Action :** crée `docker-compose.yml` à la racine.

---

## **ÉTAPE 5 : Créer `dashboard/Dockerfile` et `dashboard/nginx.conf` (production frontend)**

En production, le dashboard est **compilé** (`npm run build`) puis servi par Nginx.

### `dashboard/.dockerignore`

```dockerignore
node_modules/
dist/
.env
.env.*
```

### `dashboard/Dockerfile`

```dockerfile
# ── Dashboard CMU — build multi-étapes ──────────────────────────────────────

# Étape 1 : compilation Vite
FROM node:22-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# URL de l'API injectée au BUILD (obligatoire pour Vite)
ARG VITE_API_URL=http://127.0.0.1:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Étape 2 : servir les fichiers statiques
FROM nginx:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### `dashboard/nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Fichiers statiques React (cache long)
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA : toutes les routes inconnues → index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy vers l'API backend (même domaine, évite les problèmes CORS)
    # Décommente si tu veux un seul domaine en prod :
    #
    # location /api/ {
    #     proxy_pass http://api:8000/;
    #     proxy_http_version 1.1;
    #     proxy_set_header Upgrade $http_upgrade;
    #     proxy_set_header Connection "upgrade";
    #     proxy_set_header Host $host;
    #     proxy_set_header X-Real-IP $remote_addr;
    # }
    #
    # location /socket.io/ {
    #     proxy_pass http://api:8000/socket.io/;
    #     proxy_http_version 1.1;
    #     proxy_set_header Upgrade $http_upgrade;
    #     proxy_set_header Connection "upgrade";
    #     proxy_set_header Host $host;
    # }
}
```

**Note Vite :** `VITE_API_URL` est figée **au moment du build**. En prod, passe l'URL publique de l'API :
```bash
docker build --build-arg VITE_API_URL=https://api-cmu.entreprise.ci -f dashboard/Dockerfile ./dashboard
```

**✅ Action :** crée les 3 fichiers dans `dashboard/`.

---

## **ÉTAPE 6 : Créer `docker-compose.prod.yml` (production)**

Fichier utilisé **sur le serveur de la boîte**. Pas de volumes de code source : images figées.

```yaml
# docker-compose.prod.yml — Environnement de PRODUCTION
# Usage sur le serveur : docker compose -f docker-compose.prod.yml up -d

services:

  db:
    image: postgres:16-alpine
    container_name: cmu_db_prod
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-cmu_simulator}
    volumes:
      - postgres_data_prod:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB:-cmu_simulator}"]
      interval: 10s
      timeout: 5s
      retries: 5
    # Pas de port exposé vers l'extérieur — accessible uniquement par le réseau Docker

  api:
    image: ${API_IMAGE:-ghcr.io/VOTRE_ORG/simulateur-v5-api:latest}
    container_name: cmu_api_prod
    restart: always
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-cmu_simulator}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
      ANOMALIES_ENABLED: ${ANOMALIES_ENABLED:-false}
      ANOMALIES_RATE: ${ANOMALIES_RATE:-0.0}
      SEED_ON_START: ${SEED_ON_START:-false}
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - reports_output_prod:/app/reports/output

  dashboard:
    image: ${DASHBOARD_IMAGE:-ghcr.io/VOTRE_ORG/simulateur-v5-dashboard:latest}
    container_name: cmu_dashboard_prod
    restart: always
    depends_on:
      - api
    ports:
      - "${DASHBOARD_PORT:-8080}:80"

volumes:
  postgres_data_prod:
  reports_output_prod:
```

**Remplace `VOTRE_ORG`** par ton organisation GitHub (ex. `ghcr.io/cnam-ci/simulateur-v5-api:latest`).

**✅ Action :** crée `docker-compose.prod.yml` à la racine.

---

## **ÉTAPE 7 : Créer `.env.example`**

Modèle documenté — **copie en `.env` localement, jamais commité**.

```dotenv
# ── PostgreSQL ─────────────────────────────────────────────────────────────
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme_dev
POSTGRES_DB=cmu_simulator

# ── Backend API ──────────────────────────────────────────────────────────────
# En Docker dev : host = "db" (nom du service). En local sans Docker : "localhost"
DATABASE_URL=postgresql+asyncpg://postgres:changeme_dev@db:5432/cmu_simulator

# Clé secrète JWT — OBLIGATOIRE en prod (génère une valeur aléatoire longue)
JWT_SECRET_KEY=dev-secret-change-me-en-production

# Origines autorisées CORS (séparées par des virgules)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# ── Frontend ─────────────────────────────────────────────────────────────────
# URL publique de l'API telle que vue par le navigateur
VITE_API_URL=http://127.0.0.1:8000

# ── Seed & anomalies ─────────────────────────────────────────────────────────
SEED_ON_START=false
ANOMALIES_ENABLED=false
ANOMALIES_RATE=0.0

# ── Production (docker-compose.prod.yml) ─────────────────────────────────────
# API_IMAGE=ghcr.io/VOTRE_ORG/simulateur-v5-api:latest
# DASHBOARD_IMAGE=ghcr.io/VOTRE_ORG/simulateur-v5-dashboard:latest
# API_PORT=8000
# DASHBOARD_PORT=8080
```

**✅ Action :**
1. Crée `.env.example` à la racine
2. Copie-le en `.env` : `cp .env.example .env` (Linux/Mac) ou manuellement sous Windows
3. Vérifie que `.env` est bien dans `.gitignore`

---

## **ÉTAPE 8 : Modifier `api/main.py` — CORS configurable**

**Pourquoi :** en prod, les origines autorisées ne sont plus `localhost:5173` mais le domaine de la boîte.

**Avant** (lignes ~58-65) :
```python
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    ...
)
```

**Après** — ajoute l'import `os` en haut si absent, puis remplace le bloc CORS :

```python
import os

# ...

# Origines CORS lues depuis l'environnement (dev + prod)
_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
_cors_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**✅ Action :** modifie `api/main.py`, sauvegarde.

---

## **ÉTAPE 9 : Modifier `dashboard/vite.config.ts` — compatible Docker dev**

**Avant :**
```typescript
server: { host: "127.0.0.1", port: 5173 },
```

**Après :**
```typescript
server: {
  host: "0.0.0.0",   // accessible depuis l'extérieur du conteneur Docker
  port: 5173,
  watch: {
    usePolling: true, // nécessaire sur certains systèmes (Windows + Docker)
  },
},
```

**✅ Action :** modifie `dashboard/vite.config.ts`.

---

## **ÉTAPE 10 : Créer `.github/workflows/ci.yml` (Continuous Integration)**

Ce workflow se déclenche à **chaque push** et **chaque Pull Request**.

**Crée le dossier** `.github/workflows/` s'il n'existe pas.

```yaml
# .github/workflows/ci.yml
# Vérifie que le code compile, que le frontend build, et que l'API démarre.

name: CI — Tests & Build

on:
  push:
    branches: [main, develop, "feature/**"]
  pull_request:
    branches: [main, develop]

env:
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: ci_test_password
  POSTGRES_DB: cmu_simulator_test
  JWT_SECRET_KEY: ci-jwt-secret-not-for-production
  DATABASE_URL: postgresql+asyncpg://postgres:ci_test_password@localhost:5432/cmu_simulator_test
  CORS_ORIGINS: http://localhost:5173

jobs:

  backend:
    name: Backend — compile, migrations, smoke test
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: ci_test_password
          POSTGRES_DB: cmu_simulator_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Installer les dépendances Python
        run: pip install -r requirements.txt

      - name: Vérifier la syntaxe Python
        run: python -m compileall app api auth events kpi metrics realtime reports seed simulation

      - name: Appliquer les migrations Alembic
        run: python -m alembic upgrade head

      - name: Smoke test — l'API démarre et répond /health
        run: |
          uvicorn api.main:app --host 127.0.0.1 --port 8765 &
          SERVER_PID=$!
          for i in $(seq 1 30); do
            if curl -sf http://127.0.0.1:8765/health; then
              echo "✅ API OK"
              kill $SERVER_PID
              exit 0
            fi
            sleep 1
          done
          echo "❌ L'API n'a pas répondu à temps"
          kill $SERVER_PID || true
          exit 1

  frontend:
    name: Frontend — lint & build
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: dashboard/package-lock.json

      - name: Installer les dépendances npm
        working-directory: dashboard
        run: npm ci

      - name: Lint
        working-directory: dashboard
        run: npm run lint

      - name: Build production
        working-directory: dashboard
        env:
          VITE_API_URL: http://127.0.0.1:8000
        run: npm run build

  docker-build:
    name: Docker — build des images
    runs-on: ubuntu-latest
    needs: [backend, frontend]

    steps:
      - uses: actions/checkout@v4

      - name: Build image API
        run: docker build -t simulateur-v5-api:ci .

      - name: Build image Dashboard
        run: |
          docker build \
            --build-arg VITE_API_URL=http://127.0.0.1:8000 \
            -t simulateur-v5-dashboard:ci \
            -f dashboard/Dockerfile \
            ./dashboard
```

**Ce que fait la CI à chaque push :**

| Job            | Vérification                                      |
|----------------|---------------------------------------------------|
| `backend`      | Syntaxe Python, migrations Alembic, `/health` OK  |
| `frontend`     | Lint oxlint, build Vite sans erreur               |
| `docker-build` | Les deux Dockerfiles se construisent sans erreur  |

**✅ Action :** crée `.github/workflows/ci.yml`, commit, push → vérifie l'onglet **Actions** sur GitHub.

---

## **ÉTAPE 11 : Créer `.github/workflows/deploy.yml` (Continuous Deployment)**

Se déclenche **uniquement** quand du code est mergé sur `main`.

```yaml
# .github/workflows/deploy.yml
# Build les images, les pousse sur GitHub Container Registry, déploie sur le serveur.

name: CD — Déploiement Production

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  API_IMAGE_NAME: ${{ github.repository }}-api
  DASHBOARD_IMAGE_NAME: ${{ github.repository }}-dashboard

jobs:

  build-and-push:
    name: Build & Push images Docker
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Connexion au registre GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build & push image API
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.API_IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.API_IMAGE_NAME }}:${{ github.sha }}

      - name: Build & push image Dashboard
        uses: docker/build-push-action@v6
        with:
          context: ./dashboard
          file: ./dashboard/Dockerfile
          push: true
          build-args: |
            VITE_API_URL=${{ secrets.VITE_API_URL_PROD }}
          tags: |
            ${{ env.REGISTRY }}/${{ env.DASHBOARD_IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.DASHBOARD_IMAGE_NAME }}:${{ github.sha }}

  deploy:
    name: Déployer sur le serveur de production
    runs-on: ubuntu-latest
    needs: build-and-push
    # Décommente la ligne suivante si tu utilises un runner self-hosted sur le réseau interne :
    # runs-on: self-hosted

    steps:
      - uses: actions/checkout@v4

      - name: Déployer via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            set -e
            cd ${{ secrets.DEPLOY_PATH }}

            # Mettre à jour le fichier compose et l'env
            git pull origin main

            # Pull des nouvelles images
            echo "${{ secrets.GHCR_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
            export API_IMAGE="${{ env.REGISTRY }}/${{ env.API_IMAGE_NAME }}:latest"
            export DASHBOARD_IMAGE="${{ env.REGISTRY }}/${{ env.DASHBOARD_IMAGE_NAME }}:latest"
            docker compose -f docker-compose.prod.yml pull

            # Redémarrage sans coupure longue
            docker compose -f docker-compose.prod.yml up -d --remove-orphans

            # Migrations (idempotent — ne refait que ce qui manque)
            docker compose -f docker-compose.prod.yml exec -T api python -m alembic upgrade head

            # Nettoyage des anciennes images
            docker image prune -f

            echo "✅ Déploiement terminé."
```

**✅ Action :** crée `.github/workflows/deploy.yml`.

---

## **ÉTAPE 12 : Configurer les secrets GitHub**

Dans ton repo GitHub : **Settings → Secrets and variables → Actions → New repository secret**

| Secret               | Exemple de valeur                              | Usage                              |
|----------------------|-----------------------------------------------|------------------------------------|
| `JWT_SECRET_KEY`     | `(64 caractères aléatoires)`                  | Prod — signature JWT               |
| `POSTGRES_PASSWORD`  | `(mot de passe fort)`                         | Prod — base PostgreSQL             |
| `VITE_API_URL_PROD`  | `https://api-cmu.entreprise.ci`               | Build dashboard prod               |
| `CORS_ORIGINS`       | `https://cmu.entreprise.ci`                   | CORS prod (fichier `.env` serveur) |
| `DEPLOY_HOST`        | `10.0.1.50` ou `serveur.entreprise.ci`        | IP/hostname du serveur             |
| `DEPLOY_USER`        | `deploy`                                      | Utilisateur SSH déploiement        |
| `DEPLOY_SSH_KEY`     | `(clé privée SSH)`                            | Accès SSH sans mot de passe        |
| `DEPLOY_PATH`        | `/opt/simulateur-v5`                          | Dossier du projet sur le serveur   |
| `GHCR_TOKEN`         | `(Personal Access Token GitHub, scope packages)` | Pull images privées sur le serveur |

**Générer une clé JWT secrète :**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**✅ Action :** configure les secrets avant le premier déploiement.

---

## **ÉTAPE 13 : Préparer le serveur de production (Dédié ou 100% Gratuit)**

### Option A — Si tu as un serveur Linux dédié / d'entreprise

Script d'installation initial à exécuter **une seule fois** sur le serveur Linux (avec l'admin système).

```bash
#!/usr/bin/env bash
# install_server.sh — À exécuter une fois sur le serveur de prod
set -euo pipefail

DEPLOY_PATH="/opt/simulateur-v5"
REPO_URL="https://github.com/VOTRE_ORG/simulateur-v5.git"

# 1. Docker (si pas déjà installé)
# curl -fsSL https://get.docker.com | sh
# sudo usermod -aG docker $USER

# 2. Cloner le projet
sudo mkdir -p "$DEPLOY_PATH"
sudo chown "$USER:$USER" "$DEPLOY_PATH"
git clone "$REPO_URL" "$DEPLOY_PATH"
cd "$DEPLOY_PATH"

# 3. Fichier d'environnement prod (NE PAS committer)
cp .env.example .env
nano .env   # Remplir JWT_SECRET_KEY, POSTGRES_PASSWORD, CORS_ORIGINS, VITE_API_URL

# 4. Premier démarrage avec seed
SEED_ON_START=true docker compose -f docker-compose.prod.yml up -d

# 5. Créer le compte administrateur initial
docker compose -f docker-compose.prod.yml exec api python -m auth.bootstrap
# → Saisir email, nom, mot de passe (8 caractères min)

# 6. Remettre SEED_ON_START=false dans .env après le premier seed
```

**✅ Action :** adapte `REPO_URL` et exécute sur le serveur avec l'équipe infra.

---

### Option B — ☁️ 100% GRATUIT : Héberger sans aucun serveur payant (0€)

Si tu n'as pas de serveur dédié sous la main, voici **les meilleures solutions gratuites à vie** pour héberger le simulateur (Backend FastAPI + WebSockets, Frontend React, PostgreSQL et nom de domaine HTTPS).

#### 📊 Comparatif des solutions gratuites

| Solution | Backend (FastAPI + WebSockets) | Base PostgreSQL | Frontend (React Vite) | Nom de Domaine & SSL | Complexité |
|---|---|---|---|---|---|
| **Formule 1 : PaaS Cloud Découplé (Recommandé & le plus rapide)** | **Koyeb** ou **Render** *(Docker gratuit)* | **Neon.tech** ou **Supabase** *(Postgres managé gratuit)* | **Vercel** ou **Cloudflare Pages** *(Gratuit à vie)* | Inclus automatiquement (`*.vercel.app`, `*.koyeb.app`) avec SSL HTTPS | ⭐ Très simple (15 min) |
| **Formule 2 : VPS Cloud "Always Free" (Tout en Docker Compose)** | **Oracle Cloud Always Free** *(4 CPU ARM, 24 Go RAM, 200 Go disque gratuit à vie)* | PostgreSQL dans Docker sur le VPS | Nginx dans Docker sur le VPS | **DuckDNS** (`*.duckdns.org`) + Certbot Let's Encrypt gratuit | ⭐⭐ Moyenne (Linux + Docker) |
| **Formule 3 : Tunnel Cloudflare (Exposer depuis un PC de bureau)** | Ton PC local ou machine locale | Ton PostgreSQL local | Ton Dashboard local | **Cloudflare Tunnel** (`*.trycloudflare.com` ou domaine perso) avec SSL | ⭐ Facile (5 min) |

---

### 🌐 1. Obtenir un Nom de Domaine Gratuit avec HTTPS

Plusieurs options 100% gratuites s'offrent à toi selon la formule choisie :

#### Option 1.1 : Sous-domaines automatiques avec HTTPS (Recommandé)
Les plateformes PaaS fournissent **directement et gratuitement** des domaines sécurisés HTTPS :
- **Frontend** : `https://cmu-simulateur.vercel.app` (via Vercel)
- **Backend** : `https://cmu-api.koyeb.app` (via Koyeb) ou `https://cmu-api.onrender.com` (via Render)
- 👉 **Avantage** : Zéro achat, zéro configuration DNS complexe, renouvellement SSL automatique à vie.

#### Option 1.2 : DuckDNS (Nom de domaine personnalisé gratuit pour VPS)
Si tu utilises un VPS (ex: Oracle Cloud) ou une IP publique :
1. Rends-toi sur [duckdns.org](https://www.duckdns.org) et connecte-toi avec ton compte GitHub.
2. Choisis un sous-domaine (ex: `cmu-simulateur`). Tu obtiendras `cmu-simulateur.duckdns.org`.
3. Renseigne l'adresse IP publique de ton VPS.
4. Sur ton VPS, installe Certbot pour avoir un certificat SSL HTTPS gratuit :
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d cmu-simulateur.duckdns.org
   ```

#### Option 1.3 : FreeDNS (afraid.org) ou No-IP
- **FreeDNS** ([freedns.afraid.org](https://freedns.afraid.org/)) : Permet de créer gratuitement des sous-domaines sur plus de 50 000 domaines publics (ex: `cmu-sim.mooo.com`, `cmu.ignorelist.com`).
- **No-IP** ([noip.com](https://www.noip.com/)) : 3 sous-domaines gratuits `*.ddns.net` (nécessite une validation par email tous les 30 jours).

---

### 🚀 2. Formule 1 pas-à-pas : Déploiement PaaS Gratuit (Vercel + Koyeb/Render + Neon)

C'est la solution la plus moderne, rapide et sans maintenance de machine virtuelle.

```text
┌─────────────────────────┐          ┌─────────────────────────┐          ┌─────────────────────────┐
│   Vercel (Frontend)     │ ───────► │   Koyeb/Render (API)    │ ───────► │   Neon.tech (Postgres)  │
│ cmu-simulateur.vercel.app│ HTTPS/WS │    cmu-api.koyeb.app    │ asyncpg  │   PostgreSQL 16 Cloud   │
└─────────────────────────┘          └─────────────────────────┘          └─────────────────────────┘
```

#### Étape 2.1 : Créer la Base PostgreSQL gratuite sur Neon.tech
1. Va sur [neon.tech](https://neon.tech) et connecte-toi avec GitHub (Offre gratuite : 0.5 Go de données, illimité dans le temps).
2. Crée un projet nommé `cmu_simulator`.
3. Copie la chaîne de connexion `Connection String`. Elle ressemble à :
   ```text
   postgresql://alex:AbCdEf123@ep-cool-cloud-123456.us-east-2.aws.neon.tech/cmu_simulator?sslmode=require
   ```
4. Pour asyncpg dans FastAPI, remplace le préfixe `postgresql://` par `postgresql+asyncpg://` :
   ```text
   postgresql+asyncpg://alex:AbCdEf123@ep-cool-cloud-123456.us-east-2.aws.neon.tech/cmu_simulator?sslmode=require
   ```

#### Étape 2.2 : Déployer le Backend FastAPI + WebSockets sur Koyeb ou Render
**Avec Koyeb (Recommandé - supporte les WebSockets en continu sans veille agressive) :**
1. Crée un compte sur [koyeb.com](https://www.koyeb.com) avec GitHub.
2. Clique sur **Create Service** → Sélectionne **GitHub Repo** → Choisis ton repo `simulateur_v5`.
3. Choix du build : **Dockerfile** (il détecte automatiquement le `Dockerfile` à la racine).
4. Définis les variables d'environnement dans l'interface Koyeb :
   - `DATABASE_URL` = *(ta chaîne Neon postgresql+asyncpg://...)*
   - `JWT_SECRET_KEY` = *(ta clé générée avec secrets.token_hex(32))*
   - `CORS_ORIGINS` = `https://cmu-simulateur.vercel.app` *(ou `*` au début pour tester)*
   - `SEED_ON_START` = `true` *(uniquement pour le premier déploiement)*
   - `PORT` = `8000`
5. Clique sur **Deploy**. En 2 minutes, Koyeb te donne une URL HTTPS :
   👉 `https://cmu-api-tonnom.koyeb.app`

*(Alternative Render : Crée un "New Web Service" sur [render.com](https://render.com), lie le repo GitHub, sélectionne Docker, renseigne les mêmes variables).*

#### Étape 2.3 : Déployer le Frontend React sur Vercel
1. Va sur [vercel.com](https://vercel.com) et connecte-toi avec GitHub.
2. Clique sur **Add New...** → **Project** → Importe ton repo `simulateur_v5`.
3. Dans la configuration du projet :
   - **Framework Preset** : `Vite`
   - **Root Directory** : clique sur `Edit` et sélectionne le dossier `dashboard`
   - **Environment Variables** :
     - `VITE_API_URL` = `https://cmu-api-tonnom.koyeb.app` (l'URL de ton backend Koyeb)
4. Clique sur **Deploy**.
5. Vercel compile l'application et te fournit ton URL publique HTTPS :
   👉 `https://cmu-simulateur.vercel.app`

#### Étape 2.4 : Initialiser le compte administrateur
Pour créer le premier compte admin sur la base Neon à distance :
Depuis ton terminal local (ayant accès à Python) :
```bash
# Dans ton terminal local avec le venv activé :
DATABASE_URL="postgresql+asyncpg://alex:AbCdEf123@ep-cool-cloud-123456.us-east-2.aws.neon.tech/cmu_simulator?sslmode=require" python -m auth.bootstrap
```
🎉 **Félicitations !** Ton simulateur complet tourne 100% en ligne, avec base de données cloud, backend sécurisé, frontend CDN mondial ultra-rapide, certificats SSL HTTPS automatiques, à **0,00 €**.

---

### 🖥️ 3. Formule 2 pas-à-pas : VPS Cloud Gratuit à Vie (Oracle Cloud Always Free)

Oracle propose l'offre cloud gratuite la plus généreuse du marché mondial :
- **4 OCPU ARM Ampere + 24 Go de RAM + 200 Go de SSD gratuits à vie**.
- Tu peux y faire tourner l'intégralité du `docker-compose.prod.yml` (API, Postgres, Dashboard, Nginx, Prometheus, Grafana) sans aucune limitation !

#### Étape 3.1 : Créer le VPS Gratuit
1. Inscris-toi sur [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) (carte bancaire requise pour validation d'identité, débit de 0€).
2. Crée une instance Compute :
   - Image : **Ubuntu 22.04 LTS** ou **Ubuntu 24.04**
   - Shape : **VM.Standard.A1.Flex** (Ampere ARM - choisis par exemple 2 OCPU et 12 Go de RAM)
   - Télécharge la clé privée SSH (`ssh-key-xxxx.key`).
3. Dans la console réseau Oracle (Security List / Ingress Rules), ouvre les ports :
   - Port `80` (HTTP)
   - Port `443` (HTTPS)
   - Port `22` (SSH)

#### Étape 3.2 : Se connecter et lancer Docker Compose
```bash
# 1. Connexion SSH au VPS
ssh -i /chemin/ssh-key-xxxx.key ubuntu@IP_PUBLIQUE_ORACLE

# 2. Installer Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker

# 3. Cloner le repo
git clone https://github.com/VOTRE_ORG/simulateur_v5.git
cd simulateur_v5

# 4. Configurer le .env
cp .env.example .env
nano .env

# 5. Démarrer le simulateur complet
docker compose -f docker-compose.prod.yml up -d

# 6. Initialiser le compte admin
docker compose -f docker-compose.prod.yml exec api python -m auth.bootstrap
```

#### Étape 3.3 : Lier le nom de domaine DuckDNS gratuit
1. Crée `cmu-simulateur.duckdns.org` sur [duckdns.org](https://www.duckdns.org) pointant vers l'IP de ton VPS Oracle.
2. Installe Nginx et Certbot sur le VPS pour gérer le SSL :
```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx

# Configuration Nginx (/etc/nginx/sites-available/cmu)
sudo tee /etc/nginx/sites-available/cmu << 'EOF'
server {
    server_name cmu-simulateur.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/cmu /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Activer le certificat SSL HTTPS gratuit
sudo certbot --nginx -d cmu-simulateur.duckdns.org --non-interactive --agree-tos -m ton-email@gmail.com
```

Ton simulateur est alors accessible en ligne sur `https://cmu-simulateur.duckdns.org` !

---

### ⚡ 4. Formule 3 ultra-rapide : Cloudflare Tunnel (Zéro serveur, direct depuis ton PC)

Si tu veux faire une démo en ligne **immédiatement** à tes collègues ou clients sans louer de serveur :
1. Télécharge l'outil gratuit [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Lance simplement :
   ```bash
   cloudflared tunnel --url http://127.0.0.1:5173
   ```
3. Cloudflare te génère instantanément une URL publique sécurisée HTTPS (ex: `https://cmu-demo-xyz.trycloudflare.com`) accessible depuis n'importe où dans le monde !

---

## **ÉTAPE 14 : Premier lancement en local (Docker dev)**

```powershell
# 1. Copier les variables d'environnement
copy .env.example .env

# 2. Construire et démarrer tous les services
docker compose up --build

# 3. Dans un autre terminal — créer l'admin (première fois seulement)
docker compose exec api python -m auth.bootstrap

# 4. (Optionnel) Charger les données référentielles
docker compose exec api python -m seed
```

**URLs locales :**

| Service     | URL                              |
|-------------|----------------------------------|
| Dashboard   | http://127.0.0.1:5173            |
| API + docs  | http://127.0.0.1:8000/docs       |
| Healthcheck | http://127.0.0.1:8000/health     |

**Quand tu modifies le code ensuite :**

| Modification                        | Action requise                          |
|-------------------------------------|-----------------------------------------|
| Code Python (`api/`, `simulation/`) | Rien — `--reload` redémarre l'API       |
| Code React (`dashboard/src/`)       | Rien — Vite recharge le navigateur      |
| `requirements.txt`                  | `docker compose build api`              |
| `package.json`                      | `docker compose build dashboard`        |
| Migration Alembic                   | `docker compose exec api alembic upgrade head` |
| Variable `.env`                     | `docker compose restart api`            |

---

## **VÉRIFICATION FINALE**

### Test 1 — Docker dev démarre sans erreur

```powershell
docker compose up --build
# Attendre : "Application startup complete" dans les logs api
curl.exe http://127.0.0.1:8000/health
# → {"statut":"ok"}
```

### Test 2 — Migrations et seed

```powershell
docker compose exec api python -m alembic current
# → affiche la dernière révision

docker compose exec api python -m seed
# → "✓ Seed complété."
```

### Test 3 — Authentification

```powershell
# Remplace EMAIL et MOT_DE_PASSE par ton compte admin
curl.exe -X POST http://127.0.0.1:8000/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"admin@cmu.ci\",\"mot_de_passe\":\"votre_mot_de_passe\"}"
# → JSON avec access_token
```

### Test 4 — Build frontend prod

```powershell
docker build --build-arg VITE_API_URL=http://127.0.0.1:8000 -f dashboard/Dockerfile -t cmu-dashboard:test ./dashboard
docker run --rm -p 8080:80 cmu-dashboard:test
# → Ouvrir http://127.0.0.1:8080
```

### Test 5 — CI GitHub Actions

1. Commit tous les fichiers créés
2. Push sur une branche `feature/docker-cicd`
3. Ouvre GitHub → onglet **Actions**
4. Vérifie que les 3 jobs (`backend`, `frontend`, `docker-build`) sont ✅ verts
5. Ouvre une Pull Request vers `main`

### Test 6 — CD (staging / prod)

1. Merge la PR sur `main`
2. Vérifie le workflow **CD — Déploiement Production**
3. Sur le serveur : `docker compose -f docker-compose.prod.yml ps` → tous les services `running`

---

## **Résumé des étapes**

| #  | Fichier                              | Action    | Statut |
|----|--------------------------------------|-----------|--------|
| 1  | `.dockerignore`                      | Créer     | ☐      |
| 2  | `Dockerfile`                         | Créer     | ☐      |
| 3  | `scripts/docker-entrypoint.sh`       | Créer     | ☐      |
| 4  | `docker-compose.yml`                 | Créer     | ☐      |
| 5  | `dashboard/Dockerfile`               | Créer     | ☐      |
| 6  | `dashboard/nginx.conf`               | Créer     | ☐      |
| 7  | `dashboard/.dockerignore`            | Créer     | ☐      |
| 8  | `docker-compose.prod.yml`            | Créer     | ☐      |
| 9  | `.env.example`                       | Créer     | ☐      |
| 10 | `api/main.py`                        | Modifier  | ☐      |
| 11 | `dashboard/vite.config.ts`           | Modifier  | ☐      |
| 12 | `.github/workflows/ci.yml`           | Créer     | ☐      |
| 13 | `.github/workflows/deploy.yml`       | Créer     | ☐      |
| 14 | Secrets GitHub                       | Configurer| ☐      |
| 15 | Serveur prod                         | Installer | ☐      |
| 16 | Vérification finale                  | Tester    | ☐      |

---

## **Workflow quotidien (une fois tout en place)**

```text
1. git checkout -b feature/ma-modification
2. Tu codes (docker compose up tourne en arrière-plan)
3. git add . && git commit -m "feat: description"
4. git push origin feature/ma-modification
5. Ouvre une Pull Request sur GitHub
6. CI tourne automatiquement → tu corriges si rouge
7. Merge sur main → CD déploie sur le serveur de prod
8. Tu vérifies https://cmu.entreprise.ci
```

---

## **Dépannage courant**

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| `connection refused` sur `db` | PostgreSQL pas encore prêt | Le healthcheck + entrypoint attendent — patiente 30s |
| Bouton dashboard ne répond pas | `VITE_API_URL` incorrecte | Vérifie `.env` ; rebuild dashboard si prod |
| `401 Not authenticated` | Token JWT expiré (8h) ou secret changé | Reconnecte-toi ; vérifie `JWT_SECRET_KEY` identique partout |
| WebSocket 403 | CORS ou origine non autorisée | Ajoute l'URL du dashboard dans `CORS_ORIGINS` |
| `alembic upgrade` échoue | Migration incompatible | `docker compose exec api alembic history` ; corrige la migration |
| CI rouge sur `smoke test` | Port déjà utilisé ou import manquant | Vérifie les logs GitHub Actions |
| CD échoue sur SSH | Clé ou IP incorrecte | Vérifie secrets `DEPLOY_HOST`, `DEPLOY_SSH_KEY` |
| Dashboard prod = page blanche | `VITE_API_URL` mal passée au build | Rebuild avec `--build-arg VITE_API_URL=...` correct |
| Données perdues après `down` | Volume supprimé | Utilise `docker compose down` **sans** `-v` |

---

## **Annexe — Checklist sécurité production**

- [ ] `JWT_SECRET_KEY` : valeur aléatoire longue, jamais la valeur par défaut
- [ ] `POSTGRES_PASSWORD` : mot de passe fort, non commité
- [ ] `.env` dans `.gitignore` (vérifié)
- [ ] Port PostgreSQL **non exposé** vers Internet (interne Docker uniquement)
- [ ] HTTPS devant Nginx (certificat Let's Encrypt ou certificat interne)
- [ ] Compte admin créé via `auth.bootstrap`, pas de mot de passe par défaut
- [ ] `SEED_ON_START=false` en prod après le premier chargement
- [ ] Runner GitHub self-hosted si le serveur n'est pas accessible depuis Internet
- [ ] Sauvegardes PostgreSQL planifiées (volume `postgres_data_prod`)

---

## **À toi de jouer ! 🚀**

Commence par l'**ÉTAPE 1** :
- Crée `.dockerignore`
- Puis enchaîne les étapes dans l'ordre
- Dis-moi "ÉTAPE X OK" au fur et à mesure si tu veux qu'on avance ensemble

Ce guide couvre **tout le processus** : Docker local, CI automatique, CD vers les serveurs de la boîte, et les bonnes pratiques pour une app qui va beaucoup évoluer en production.
