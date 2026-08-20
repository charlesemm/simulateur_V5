```bash
#!/usr/bin/env bash
# Crée la base PostgreSQL puis applique toutes les migrations Alembic.

set -euo pipefail

# Les valeurs restent configurables sans modifier le fichier.
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-cmu_simulator}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD est obligatoire}"
export PGPASSWORD="${DB_PASSWORD}"

# La vérification rend le script rejouable sans écraser une base existante.
if ! psql --host="${DB_HOST}" --port="${DB_PORT}" --username="${DB_USER}" \
  --dbname="postgres" --tuples-only --no-align \
  --command="SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
  createdb --host="${DB_HOST}" --port="${DB_PORT}" \
    --username="${DB_USER}" "${DB_NAME}"
  echo "Base ${DB_NAME} créée."
else
  echo "Base ${DB_NAME} déjà présente."
fi

# Alembic reçoit la même URL que la future application.
export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
python -m alembic upgrade head
echo "Schéma CMU installé avec succès."
```

---