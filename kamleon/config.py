from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables (or a local `.env`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # `postgresql+psycopg://` works for both the async engine (the API) and the
    # sync engine (Alembic), so there is a single URL to configure.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    echo_sql: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
