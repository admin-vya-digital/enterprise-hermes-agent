from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DOCKER_API_", extra="ignore")

    app_name: str = "docker-api"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # vya-workforce-api (hermes-agent em homologação) — upstream que este
    # serviço encapsula. VYA_API_KEY vem de Docker secret (sem prefixo,
    # mesmo arquivo/credencial usado pela própria vya-workforce-api).
    vya_api_base_url: str = "http://vya-workforce-api:8700"
    vya_api_key: str = Field(default="", validation_alias="VYA_API_KEY")
    vya_api_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
