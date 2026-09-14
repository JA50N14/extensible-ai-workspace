"""Alembic migration environment."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from extensible_ai_workspace.config import DatabaseSettings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def get_migration_database_url() -> str:
    """Return the configured database URL using SQLAlchemy's Psycopg driver."""

    settings = DatabaseSettings()
    database_url = make_url(settings.database_url)

    if database_url.drivername == "postgresql":
        database_url = database_url.set(
            drivername="postgresql+psycopg"
        )

    return database_url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    """Generate migration SQL without opening a database connection."""

    context.configure(
        url=get_migration_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations using a database connection."""

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )
    configuration["sqlalchemy.url"] = get_migration_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
