"""Configure le moteur SQLAlchemy asynchrone et les sessions PostgreSQL."""

import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Charge le fichier .env local s'il existe. Les variables déjà définies dans
# l'environnement gardent la priorité : la CI n'est pas affectée.
load_dotenv()

# La valeur locale reste surchargeable pour les autres environnements.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "La variable d'environnement DATABASE_URL est obligatoire. "
        "Exemple : postgresql+asyncpg://postgres:<mot_de_passe>@localhost:5432/cmu_simulator"
    )

# Le pré-ping empêche la réutilisation d'une connexion PostgreSQL périmée.
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    """Fournit une session asynchrone et garantit sa fermeture."""

    async with async_session_factory() as session:
        yield session