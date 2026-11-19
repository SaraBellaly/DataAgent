"""
Configuration de l'application, lue dans les variables d'environnement.

Source unique : le fichier .env à la racine du dépôt (le même que pour docker compose).
Un fichier backend/.env optionnel peut surcharger des valeurs en développement.
Dans le conteneur, docker-compose.yml fournit les variables (POSTGRES_HOST=db, etc.).
"""
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_BACKEND_ENV = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "Agent de gestion de base de données"
    app_version: str = "0.2.0"
    debug: bool = False
    log_level: str = "INFO"

    # PostgreSQL (hors conteneur : base publiée sur 127.0.0.1:POSTGRES_PORT)
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "immo"

    # Rôle de l'agent : lecture seule sur immo, aucun accès au schéma app
    analyst_ro_user: str = "analyst_ro"
    analyst_ro_password: str = Field(min_length=1)

    # Rôle de l'application : comptes, sessions, historique (schéma app uniquement)
    app_agent_user: str = "app_agent"
    app_agent_password: str = Field(min_length=1)

    # Sessions (fiche de cadrage : 8 heures, cookie HttpOnly + SameSite)
    session_cookie_name: str = "session"
    session_duration_hours: int = 8
    cookie_secure: bool = False  # True dès que l'application est servie en HTTPS

    # Blocage après échecs de connexion (fiche : 5 échecs => 15 minutes)
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # Modèle de l'agent : toute API compatible OpenAI (Groq par défaut, Ollama en local…)
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = 60.0
    llm_max_output_tokens: int = 1500
    llm_tool_choice: str = "auto"      # « required » force un outil, mais gpt-oss répond alors parfois en texte refusé
    llm_max_retries: int = 2           # 429 : attend le délai annoncé par le fournisseur avant de renoncer

    # Maîtrise des tokens (plan gratuit Groq : 8 000 tokens/min) et du comportement de l'agent
    agent_max_steps: int = 6             # appels au modèle par question
    agent_history_turns: int = 4         # échanges récents de l'utilisateur renvoyés en contexte
    agent_max_tool_chars: int = 3500     # taille maximale d'un résultat d'outil envoyé au modèle
    agent_max_result_rows: int = 200     # lignes renvoyées à l'utilisateur après validation

    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, _BACKEND_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def _conninfo(self, user: str, password: str, application_name: str) -> str:
        return (
            f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            f"?application_name={application_name}"
        )

    @property
    def conninfo_ro(self) -> str:
        return self._conninfo(self.analyst_ro_user, self.analyst_ro_password, "dataagent_ro")

    @property
    def conninfo_app(self) -> str:
        return self._conninfo(self.app_agent_user, self.app_agent_password, "dataagent_app")


settings = Settings()
