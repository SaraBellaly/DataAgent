"""
Configuration de l'application via variables d'environnement.
Utilise pydantic-settings pour la validation et le chargement automatique depuis .env
"""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application chargée depuis les variables d'environnement."""

    # Application
    app_name: str = Field(default="AI Database Engineer API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # PostgreSQL - Connexion lecture seule (données immobilières DVF/INSEE)
    # Utilise le rôle analyst_ro : lecture seule, timeout 30s
    postgres_host: str = Field(alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_user_ro: str = Field(alias="POSTGRES_USER_RO")
    postgres_password_ro: str = Field(alias="POSTGRES_PASSWORD_RO")

    # PostgreSQL - Connexion données applicatives (future)
    # Pour authentification, utilisateurs, historique des conversations
    # app_db_host: str | None = Field(default=None, alias="APP_DB_HOST")
    # app_db_port: int | None = Field(default=None, alias="APP_DB_PORT")
    # app_db_name: str | None = Field(default=None, alias="APP_DB_NAME")
    # app_db_user: str | None = Field(default=None, alias="APP_DB_USER")
    # app_db_password: str | None = Field(default=None, alias="APP_DB_PASSWORD")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="CORS_ORIGINS"
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Si c'est une string JSON
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Sinon, split par virgules
                return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def database_url_ro(self) -> str:
        """URL de connexion PostgreSQL en lecture seule (analyst_ro)."""
        return (
            f"postgresql://{self.postgres_user_ro}:{self.postgres_password_ro}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # @property
    # def database_url_app(self) -> str | None:
    #     """URL de connexion PostgreSQL données applicatives (future)."""
    #     if not all([self.app_db_host, self.app_db_name, self.app_db_user, self.app_db_password]):
    #         return None
    #     return (
    #         f"postgresql://{self.app_db_user}:{self.app_db_password}"
    #         f"@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"
    #     )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Instance globale des settings (singleton)
settings = Settings()
