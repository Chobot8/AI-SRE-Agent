"""Application configuration.

Settings are loaded from environment variables (and an optional .env file).
Never commit real secrets -- see .env.example for the expected variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Values are read from environment variables. A local `.env` file is loaded
    automatically during development. Secrets must stay out of version control.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service metadata ---
    app_name: str = "AI SRE Agent"
    environment: str = "local"
    debug: bool = True

    # --- Observability (KAN-12) ---
    log_level: str = "INFO"
    log_format: str = "json"  # "json" (structured) or "text"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- LLM / provider placeholders (no real values committed) ---
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # --- Vector store placeholder (used from KAN-4 onward) ---
    vector_store_url: str | None = None

    # --- Database (KAN-16) ---
    # SQLAlchemy URL for the PostgreSQL persistence layer. None disables the DB
    # (the agent still runs in-memory). docker-compose sets this to the `db`
    # service; for host-local dev use localhost. See .env.example.
    database_url: str | None = None
    db_schema: str = "sre"
    db_echo: bool = False

    # --- SRE tool connectors (KAN-22) ---
    # All optional. Unset (default) keeps every real connector inert -- it
    # returns a `not_configured` ConnectorError rather than making a network
    # call, which is how the local demo runs with zero production credentials.
    # See backend/connectors/README.md.
    prometheus_base_url: str | None = None
    prometheus_timeout_seconds: float = 5.0

    loki_base_url: str | None = None
    loki_timeout_seconds: float = 5.0

    kubernetes_api_base_url: str | None = None
    kubernetes_bearer_token: str | None = None
    kubernetes_verify_tls: bool = True
    kubernetes_timeout_seconds: float = 5.0

    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_timeout_seconds: float = 5.0

    runbook_source_base_url: str | None = None
    runbook_source_api_token: str | None = None
    runbook_timeout_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
