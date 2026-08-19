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
RUN pip install --no-cache-dir --default-timeout=120 --retries=10 -r requirements.txt

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

# Script d'entrée : convertir les fins de lignes Windows (CRLF -> LF), droits d'exécution
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

# Utilisateur non-root (bonne pratique sécurité)
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]

# Point d'entrée ASGI : api.main:app inclut Socket.IO
# En prod : pas de --reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]