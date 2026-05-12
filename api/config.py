"""
Configuration module for Research OS.

Loads environment variables and provides typed configuration.
"""

from functools import lru_cache
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Research OS", alias="APP_NAME")
    app_version: str = Field(default="0.3.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="research_os", alias="POSTGRES_USER")
    postgres_password: str = Field(default="research_os_dev", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="research_os", alias="POSTGRES_DB")

    @property
    def postgres_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def sync_postgres_url(self) -> str:
        """Generate synchronous PostgreSQL connection URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    @property
    def redis_url(self) -> str:
        """Generate Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0", alias="CELERY_RESULT_BACKEND"
    )

    # Ollama (Local Models)
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3", alias="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=120, alias="OLLAMA_TIMEOUT")

    # Cloud Providers (Phase 5)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")

    # Model Routing
    prefer_local_models: bool = Field(default=True, alias="PREFER_LOCAL_MODELS")
    enable_cloud_fallback: bool = Field(default=True, alias="ENABLE_CLOUD_FALLBACK")
    local_model_timeout: int = Field(default=120, alias="LOCAL_MODEL_TIMEOUT")
    cloud_model_timeout: int = Field(default=180, alias="CLOUD_MODEL_TIMEOUT")

    # Cost Management
    max_cost_per_request: float = Field(default=1.0, alias="MAX_COST_PER_REQUEST")
    max_cost_per_session: float = Field(default=10.0, alias="MAX_COST_PER_SESSION")
    max_tokens_per_request: int = Field(default=8192, alias="MAX_TOKENS_PER_REQUEST")
    max_tokens_per_session: int = Field(default=100000, alias="MAX_TOKENS_PER_SESSION")

    # GPU Settings
    gpu_memory_threshold: float = Field(default=0.9, alias="GPU_MEMORY_THRESHOLD")
    enable_gpu_monitoring: bool = Field(default=True, alias="ENABLE_GPU_MONITORING")

    # Vector Store (Phase 3 - RAG Infrastructure)
    vector_store_provider: str = Field(default="chroma", alias="VECTOR_STORE_PROVIDER")
    chroma_persist_dir: str = Field(default="./chroma_data", alias="CHROMA_PERSIST_DIR")

    # Qdrant (production vector store)
    qdrant_url: Optional[str] = Field(default=None, alias="QDRANT_URL")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_vector_size: int = Field(default=768, alias="QDRANT_VECTOR_SIZE")

    # Embedding Model
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")

    # Memory Settings
    max_episodic_entries: int = Field(default=1000, alias="MAX_EPISODIC_ENTRIES")
    max_semantic_entries: int = Field(default=10000, alias="MAX_SEMANTIC_ENTRIES")
    compression_threshold: int = Field(default=50, alias="COMPRESSION_THRESHOLD")
    session_ttl: int = Field(default=604800, alias="SESSION_TTL")  # 7 days

    # RAG Settings
    rag_chunk_size: int = Field(default=1000, alias="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=200, alias="RAG_CHUNK_OVERLAP")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")

    # Reflection Settings
    max_reflections: int = Field(default=3, alias="MAX_REFLECTIONS")
    hallucination_threshold: float = Field(default=0.4, alias="HALLUCINATION_THRESHOLD")
    confidence_threshold: float = Field(default=0.5, alias="CONFIDENCE_THRESHOLD")

    # LangSmith
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_api_key: Optional[str] = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="research-agent", alias="LANGSMITH_PROJECT")

    # Security
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(default=60, alias="JWT_EXPIRATION_MINUTES")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from comma-separated string or JSON array."""
        if isinstance(v, str):
            # Handle comma-separated string format from .env
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v if isinstance(v, list) else [v]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.environment.lower() == "test"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
