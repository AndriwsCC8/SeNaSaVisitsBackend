"""Configuración del entorno de Alembic.

La URL de conexión se toma de la variable de entorno DATABASE_URL (vía Settings),
nunca se escribe directamente en alembic.ini. El `target_metadata` apunta a la
`Base` declarativa de SQLAlchemy con los modelos ORM registrados desde el módulo
central de persistencia.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.persistence import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# ConfigParser treats percent signs as interpolation markers. Escape them so
# URL-encoded ODBC parameters survive until SQLAlchemy parses the URL.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# Los imports anteriores registran todas las tablas antes de obtener metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
