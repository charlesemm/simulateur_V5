"""Configure Alembic pour le moteur SQLAlchemy asynchrone."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base

# Sans cela, DATABASE_URL n'est lue que si elle est déjà exportée dans le
# shell : Alembic retombait sur l'URL du fichier INI et échouait à se
# connecter, alors que l'API démarrait sans problème.
load_dotenv()


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# L'environnement est prioritaire sur l'URL locale du fichier INI.
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url")),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Génère le SQL sans ouvrir de connexion à PostgreSQL."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_synchronous_migrations(connection: Connection) -> None:
    """Exécute Alembic sur l'adaptateur synchrone de la connexion async."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Ouvre la connexion async et applique les migrations."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(run_synchronous_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())