import logging.config

from dependency_injector import containers, providers
from infra.database import Database
from infra.settings import Settings


class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)

    logging = providers.Resource(
        logging.config.fileConfig,
        fname=settings().logging_configuration_file,
    )

    database = providers.ThreadSafeSingleton(
        Database, db_dsn=settings().pg_dsn, db_echo=settings().engine_echo
    )
