"""
Centralized application configuration.
All values are overridable via environment variables / .env file.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "GraphRAG Research Assistant"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = Field(default="change-me-in-prod")
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # --- LLM Providers ---
    LLM_PROVIDER: Literal["groq", "openai", "gemini"] = "gemini"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_EXTRACTION_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EXTRACTION_MODEL: str = "gpt-4o-mini"
    # Gemini is reached through Google's OpenAI-compatible endpoint, so it
    # reuses the `openai` SDK below rather than needing its own client lib.
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EXTRACTION_MODEL: str = "gemini-2.5-flash-lite"

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384
    EMBEDDING_DEVICE: str = "cpu"

    # --- Neo4j ---
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "graphrag_password"
    NEO4J_DATABASE: str = "neo4j"

    # --- Qdrant ---
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "research_chunks"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # --- Storage ---
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = 50

    # --- SQL metadata DB (papers, jobs, users) ---
    DATABASE_URL: str = "sqlite+aiosqlite:////data/app.db"

    # --- Chunking ---
    CHUNK_SIZE_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 64

    # --- Entity extraction ---
    # Chunks per LLM call during extraction. Higher = fewer calls & less
    # repeated system-prompt overhead, but larger risk of truncated/malformed
    # JSON responses if the model's output gets too long. 6 is a reasonable
    # default for typical chunk sizes (~512 tokens) against a 70B-class model.
    ENTITY_EXTRACTION_BATCH_SIZE: int = 6

    # --- Retry / ingestion ---
    INGEST_MAX_RETRIES: int = 3
    INGEST_RETRY_BACKOFF_SECONDS: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
