# ═══════════════════════════════════════════════════════════════
# ÉCHO — Image multi-étage pour Podman (et Docker)
#
# Étage 1 : compile le dashboard React
# Étage 2 : installe les dépendances Python
# Étage 3 : image finale légère
# ═══════════════════════════════════════════════════════════════

# ── Étage 1 : dashboard ─────────────────────────────────────────
FROM docker.io/library/node:22-alpine AS dashboard

WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./

# `--legacy-peer-deps` : recharts 2.13 declare ne supporter React que jusqu'a
# la version 18, alors que le dashboard tourne en React 19. Le conflit est
# theorique — les graphiques fonctionnent — mais `npm ci` refuse d'installer
# sans cette tolerance, et la construction de l'image echouait.
#
# Le verrou (package-lock.json) reste souverain : l'arbre installe ici est
# exactement celui du poste de developpement, ni plus ni moins. A revoir en
# passant a recharts 3, qui accepte React 19 officiellement.
RUN npm ci --ignore-scripts --legacy-peer-deps
COPY dashboard/ ./
RUN npm run build


# ── Étage 2 : dépendances Python ────────────────────────────────
FROM docker.io/library/python:3.14-slim AS deps

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# ── Étage 3 : image finale ──────────────────────────────────────
FROM docker.io/library/python:3.14-slim

# Sécurité : utilisateur non-root
RUN groupadd -r echo && useradd -r -g echo -d /app -s /sbin/nologin echo

WORKDIR /app

# Dépendances Python depuis l'étage 2
COPY --from=deps /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Code source
COPY . .

# Dashboard compilé depuis l'étage 1
COPY --from=dashboard /app/dashboard/dist /app/dashboard/dist

# Dossier de sortie des rapports (volume en production)
RUN mkdir -p /app/reports/output && chown -R echo:echo /app

USER echo

# L'API écoute sur le port 8000
EXPOSE 8000

# Uvicorn avec un seul worker (asyncio gère la concurrence)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
