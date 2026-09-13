"""
SafeVision AI — Application Configuration

Reads all settings from environment variables (via .env file or system env).
Never hardcodes secrets. Uses pydantic-settings for validation and type coercion.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "SafeVision AI"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8000

    # --- Database ---
    database_url: str = "postgresql://safevision:safevision_dev@localhost:5432/safevision_db"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT / Auth ---
    jwt_secret_key: str = "CHANGE_ME_TO_A_RANDOM_SECRET_AT_LEAST_32_CHARS"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # --- Rate Limiting ---
    rate_limit_auth: str = "5/minute"
    rate_limit_default: str = "60/minute"

    # --- Evidence Storage ---
    evidence_storage_backend: str = "local"
    evidence_local_path: str = "./evidence_storage"

    # --- Email Notifications ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None

    # --- WhatsApp (Twilio) ---
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_content_sid: str | None = None  # Content Template SID (HX...) — required when account enforces templates

    # --- AI/RAG ---
    llm_api_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    # --- Phase 9: LLM Provider Configuration ---
    llm_provider: str = "gemini"           # gemini | ollama
    llm_mode: str = "primary_only"         # primary_only | fallback
    llm_primary_provider: str = "gemini"
    llm_fallback_provider: str = "ollama"

    # Gemini
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"

    # OpenRouter (Phase 14 — multimodal via Gemma)
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemma-4-26b-a4b-it:free"

    # Generation parameters
    llm_timeout_seconds: int = 60
    llm_max_output_tokens: int = 8192
    llm_temperature: float = 0.3

    # --- RAG / Knowledge Base (Phase 8) ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512       # Characters per chunk
    chunk_overlap: int = 64     # Character overlap between chunks
    chromadb_persist_dir: str = "./chromadb_data"
    max_document_size_bytes: int = 10_000_000  # 10 MB
    rag_default_top_k: int = 5

    # --- CV Models & Video Ingestion (Phase 11) ---
    cv_ppe_model_path: str = "../models/ppe/best.pt"
    cv_fire_smoke_model_path: str = "../models/fire_smoke/best.pt"
    video_upload_dir: str = "./tmp/safevision_uploads"
    max_video_upload_bytes: int = 104_857_600  # 100 MB

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def log_level_int(self) -> int:
        """Convert string log level to Python logging integer."""
        return getattr(logging, self.log_level.upper(), logging.INFO)


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Call get_settings() wherever config is needed — the lru_cache ensures
    env vars are only parsed once per process lifetime.
    """
    return Settings()
