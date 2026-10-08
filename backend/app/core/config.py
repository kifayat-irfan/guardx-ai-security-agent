"""GuardX configuration — everything comes from environment variables.

Copy `.env.example` to `.env` at the repo root. Never hardcode secrets.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",  # backend/.env fallback
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "dev"
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    app_version: str = "0.1.0"

    # Database
    database_url: str = (
        "postgresql+psycopg2://guardx:change_me_in_production"
        "@localhost:5432/guardx"
    )

    # ChromaDB (health check only in Phase 1)
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # RAG (Phase 4) — local persistent ChromaDB, local embeddings
    rag_policies_dir: str = "../policies"  # relative to backend/
    chroma_persist_dir: str = "./data/chroma"  # relative to backend/
    chroma_collection: str = "guardx_policies"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Local LLM (Phase 5) — Ollama via LangChain; optional, never required.
    # Empty = provider default (applied in app/langchain/llm.py).
    llm_provider: str = "ollama"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = 30.0

    # SenseNova LLM (post-Phase-10) — real API analysis via LangChain.
    # Set LLM_PROVIDER=sensenova. The key lives ONLY in the gitignored .env.
    # NOTE (2026-10-08): the account is on the INTERNATIONAL platform
    # (platform.sensenova.ai) — the API root is token.sensenova.ai, NOT
    # the China token.sensenova.cn. Keys are platform-specific.
    sensenova_api_key: str = ""
    sensenova_base_url: str = "https://token.sensenova.ai/v1"
    sensenova_model: str = "sensenova-6.8-flash-lite"
    sensenova_max_tokens: int = 1024
    sensenova_retries: int = 1  # extra attempts for network/5xx/timeout only

    # Vision (Phase 2)
    yolo_model: str = "yolov8n.pt"
    yolo_confidence: float = 0.5
    yolo_imgsz: int = 640
    frame_skip: int = 2  # process every Nth frame (CPU-friendly)

    # n8n automation (Phase 9) — optional, DISABLED by default.
    # GuardX works fully without n8n; the webhook only fires when enabled.
    n8n_enabled: bool = False
    n8n_webhook_url: str = ""
    n8n_webhook_secret: str = ""
    n8n_webhook_timeout_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
