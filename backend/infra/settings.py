import pathlib

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pg_dsn: PostgresDsn
    engine_echo: bool = False
    logging_configuration_file: pathlib.Path

    pdf_data_dir: pathlib.Path
    min_chars_for_page: int = 10
    seuil_qualite_texte_pdf: float = 0.3
    gradio_user: str
    gradio_password: str

    model_config = SettingsConfigDict(env_prefix="CPDA_")
