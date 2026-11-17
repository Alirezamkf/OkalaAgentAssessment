"""Configure the Alembic environment for database migrations.

Alembic manages schema changes as versioned migrations. This file obtains the
URL from the application settings and exposes the shared model metadata for
autogeneration, without creating any initial table or migration.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.database.base import Base
from app.models import Exam, HRUser, Question  # noqa: F401 - Register model tables in metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models before inspection so their tables are registered in metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a connection and generate executable SQL."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through a synchronous engine and an active connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    connectable = engine_from_config(
        configuration,
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
