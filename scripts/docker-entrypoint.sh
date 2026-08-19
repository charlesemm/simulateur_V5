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