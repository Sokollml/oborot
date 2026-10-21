"""Настройка Alembic: берём адрес базы из настроек приложения и схему из app.models."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Тесты могут передать свой адрес через config.attributes["database_url"].
config.set_main_option("sqlalchemy.url", config.attributes.get("database_url", settings.database_url))
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
