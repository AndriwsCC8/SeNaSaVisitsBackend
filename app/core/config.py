"""Configuración centralizada de la aplicación, cargada desde variables de entorno."""
from enum import Enum
from functools import lru_cache
import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("senasa_visits")


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_name: str = "SeNaSa Visits API"
    environment: Environment = Environment.DEVELOPMENT
    api_v1_prefix: str = "/api"

    # Base de datos (SQL Server vía PyODBC)
    database_url: str

    # JWT (preparado para autenticación futura)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 10080

    # CORS
    cors_origins: str = (
        "http://localhost:5173,http://localhost:8443,https://localhost:8443,"
        "http://127.0.0.1:8443,https://127.0.0.1:8443"
    )
    # La API usa Authorization: Bearer; no requiere cookies, por lo que queda desactivado.
    cors_allow_credentials: bool = False

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        if "*" in self.cors_origins_list:
            raise ValueError("CORS_ORIGINS no admite '*'; liste los orígenes explícitos.")
        return self

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if len(self.jwt_secret_key) < 32:
            message = "JWT_SECRET_KEY debe tener al menos 32 caracteres para HS256."
            if self.environment == Environment.PRODUCTION:
                raise ValueError(message)
            logger.warning(message)
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia de Settings cacheada (una sola lectura del entorno)."""
    return Settings()
