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

    # Vision (Phase 2)
    yolo_model: str = "yolov8n.pt"
    yolo_confidence: float = 0.5
    yolo_imgsz: int = 640
    frame_skip: int = 2  # process every Nth frame (CPU-friendly)


@lru_cache
def get_settings() -> Settings:
    return Settings()
