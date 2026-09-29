"""Centralized application configuration for Prompt Compiler."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from a local .env file if present
load_dotenv()


def _get_env_float(key: str, default: float) -> float:
    """Safely parse a float from an environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _get_env_int(key: str, default: int) -> int:
    """Safely parse an int from an environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """Safely parse a boolean from an environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _resolve_data_dir() -> str | None:
    """Safely resolve configured application data directory."""
    raw = os.getenv("PROMPT_COMPILER_DATA_DIR") or os.getenv("APP_DATA_DIR")
    if raw and raw.strip():
        return os.path.abspath(os.path.expanduser(raw.strip()))
    return None


def _resolve_database_url() -> str:
    """Resolve database URL with fallback to data directory or local dev path."""
    explicit = os.getenv("DATABASE_URL")
    if explicit and explicit.strip():
        return explicit.strip()
    data_dir = _resolve_data_dir()
    if data_dir:
        return f"sqlite:///{os.path.join(data_dir, 'prompt_compiler.db')}"
    return "sqlite:///./data/prompt_compiler.db"


DEFAULT_CLERK_JWT_KEY: str = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAttcIsP3IL/wwhw4QoGJ3\n"
    "ijtdJzvL1GbgYFFS7YVPj9XTHAz6ltKT758rYNywAqShd8Vz7IxRKA2GTWg/Mpdq\n"
    "3TswYUbo6FVnTvWU+5jTNeW/654vK30xMFeaD7j4SH4pFjpCBQj+zPO2f88UprWr\n"
    "KzB54CKFe8ajvDM/IgiKcZGughjchW2BfL3M3zovta33RKujX2zxmBJAhDgA5hci\n"
    "8QQxduHnKkRY+lM7IbWr4bwI8Dvqq295sOZiUTQWI0l5mo4ywlJ8m/+wr5l4fz/C\n"
    "9Ib6p5pujudHYxB0iiOrwA7Dje6pKdyegUCASh/tH3hWB7iMx4TW7Q8d0g5Z/ulX\n"
    "9wIDAQAB\n"
    "-----END PUBLIC KEY-----"
)


@dataclass(frozen=True)
class Settings:
    """Application settings with environment variable override support."""

    APP_NAME: str = os.getenv("APP_NAME", "Prompt Compiler")
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.1")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
    OLLAMA_TIMEOUT: float = _get_env_float("OLLAMA_TIMEOUT", 120.0)
    MAX_REFINEMENT_ITERATIONS: int = _get_env_int("MAX_REFINEMENT_ITERATIONS", 2)
    MAX_INTERVIEW_QUESTIONS: int = _get_env_int("MAX_INTERVIEW_QUESTIONS", 3)
    INTERVIEW_SESSION_TTL_SECONDS: float = _get_env_float("INTERVIEW_SESSION_TTL_SECONDS", 3600.0)
    MAX_INTERVIEW_TURNS: int = _get_env_int("MAX_INTERVIEW_TURNS", 3)
    APP_DATA_DIR: str | None = _resolve_data_dir()
    DATABASE_URL: str = _resolve_database_url()
    DATABASE_ECHO: bool = os.getenv("DATABASE_ECHO", "false").lower() in ("true", "1", "yes")
    DESKTOP_MODE: bool = _get_env_bool("DESKTOP_MODE", False)
    DESKTOP_BACKEND_HOST: str = os.getenv("DESKTOP_BACKEND_HOST", os.getenv("BACKEND_HOST", "127.0.0.1"))
    DESKTOP_BACKEND_PORT: int = _get_env_int("DESKTOP_BACKEND_PORT", _get_env_int("BACKEND_PORT", 8000))
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_DIMENSION: int = _get_env_int("EMBEDDING_DIMENSION", 768)
    CHUNK_SIZE: int = _get_env_int("CHUNK_SIZE", 500)
    CHUNK_OVERLAP: int = _get_env_int("CHUNK_OVERLAP", 100)
    KNOWLEDGE_SEARCH_TOP_K: int = _get_env_int("KNOWLEDGE_SEARCH_TOP_K", 5)
    VECTOR_METRIC: str = os.getenv("VECTOR_METRIC", "cosine")
    KNOWLEDGE_RETRIEVAL_ENABLED: bool = _get_env_bool("KNOWLEDGE_RETRIEVAL_ENABLED", True)
    KNOWLEDGE_MIN_RELEVANCE_SCORE: float = _get_env_float("KNOWLEDGE_MIN_RELEVANCE_SCORE", 0.5)
    KNOWLEDGE_RETRIEVAL_TOP_K: int = _get_env_int("KNOWLEDGE_RETRIEVAL_TOP_K", 3)
    KNOWLEDGE_MAX_CONTEXT_CHARS: int = _get_env_int("KNOWLEDGE_MAX_CONTEXT_CHARS", 2000)
    DOCUMENT_INGESTION_ENABLED: bool = _get_env_bool("DOCUMENT_INGESTION_ENABLED", True)
    DOCUMENT_MAX_FILE_SIZE_BYTES: int = _get_env_int("DOCUMENT_MAX_FILE_SIZE_BYTES", 1048576)
    KNOWLEDGE_MAX_RETRIEVAL_QUERIES: int = _get_env_int("KNOWLEDGE_MAX_RETRIEVAL_QUERIES", 3)
    KNOWLEDGE_SOURCE_WEIGHTING_ENABLED: bool = _get_env_bool("KNOWLEDGE_SOURCE_WEIGHTING_ENABLED", True)
    KNOWLEDGE_SOURCE_DIVERSITY_ENABLED: bool = _get_env_bool("KNOWLEDGE_SOURCE_DIVERSITY_ENABLED", True)
    KNOWLEDGE_SOURCE_DIVERSITY_MIN_SCORE_RATIO: float = _get_env_float("KNOWLEDGE_SOURCE_DIVERSITY_MIN_SCORE_RATIO", 0.8)
    CLERK_SECRET_KEY: str | None = os.getenv("CLERK_SECRET_KEY")
    CLERK_JWT_KEY: str | None = os.getenv("CLERK_JWT_KEY", DEFAULT_CLERK_JWT_KEY)
    CLERK_PUBLISHABLE_KEY: str | None = os.getenv(
        "CLERK_PUBLISHABLE_KEY",
        "pk_test_bW9kZWwtY29icmEtNzA4Ni5jbGVyay5hY2NvdW50cy5kZXYk",
    )
    CLERK_AUTHORIZED_PARTIES: str = os.getenv(
        "CLERK_AUTHORIZED_PARTIES",
        "http://localhost:5173,tauri://localhost,http://tauri.localhost,http://127.0.0.1:18000,http://localhost:18000,http://127.0.0.1:18001,http://localhost:18001,http://127.0.0.1:8000,http://localhost:8000",
    )

    @property
    def knowledge_max_retrieval_queries(self) -> int:
        return self.KNOWLEDGE_MAX_RETRIEVAL_QUERIES

    @property
    def knowledge_source_weighting_enabled(self) -> bool:
        return self.KNOWLEDGE_SOURCE_WEIGHTING_ENABLED

    @property
    def knowledge_source_diversity_enabled(self) -> bool:
        return self.KNOWLEDGE_SOURCE_DIVERSITY_ENABLED

    @property
    def knowledge_source_diversity_min_score_ratio(self) -> float:
        return self.KNOWLEDGE_SOURCE_DIVERSITY_MIN_SCORE_RATIO

    @property
    def document_ingestion_enabled(self) -> bool:
        return self.DOCUMENT_INGESTION_ENABLED

    @property
    def document_max_file_size_bytes(self) -> int:
        return self.DOCUMENT_MAX_FILE_SIZE_BYTES

    @property
    def app_name(self) -> str:
        return self.APP_NAME

    @property
    def app_version(self) -> str:
        return self.APP_VERSION

    @property
    def ollama_base_url(self) -> str:
        return self.OLLAMA_BASE_URL

    @property
    def ollama_model(self) -> str:
        return self.OLLAMA_MODEL

    @property
    def ollama_timeout(self) -> float:
        return self.OLLAMA_TIMEOUT

    @property
    def max_refinement_iterations(self) -> int:
        return self.MAX_REFINEMENT_ITERATIONS

    @property
    def max_interview_questions(self) -> int:
        return self.MAX_INTERVIEW_QUESTIONS

    @property
    def interview_session_ttl_seconds(self) -> float:
        return self.INTERVIEW_SESSION_TTL_SECONDS

    @property
    def max_interview_turns(self) -> int:
        return self.MAX_INTERVIEW_TURNS

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def database_echo(self) -> bool:
        return self.DATABASE_ECHO

    @property
    def embedding_provider(self) -> str:
        return self.EMBEDDING_PROVIDER

    @property
    def embedding_model(self) -> str:
        return self.EMBEDDING_MODEL

    @property
    def embedding_dimension(self) -> int:
        return self.EMBEDDING_DIMENSION

    @property
    def chunk_size(self) -> int:
        return self.CHUNK_SIZE

    @property
    def chunk_overlap(self) -> int:
        return self.CHUNK_OVERLAP

    @property
    def knowledge_search_top_k(self) -> int:
        return self.KNOWLEDGE_SEARCH_TOP_K

    @property
    def vector_metric(self) -> str:
        return self.VECTOR_METRIC

    @property
    def knowledge_retrieval_enabled(self) -> bool:
        return self.KNOWLEDGE_RETRIEVAL_ENABLED

    @property
    def knowledge_min_relevance_score(self) -> float:
        return self.KNOWLEDGE_MIN_RELEVANCE_SCORE

    @property
    def knowledge_retrieval_top_k(self) -> int:
        return self.KNOWLEDGE_RETRIEVAL_TOP_K

    @property
    def knowledge_max_context_chars(self) -> int:
        return self.KNOWLEDGE_MAX_CONTEXT_CHARS

    @property
    def clerk_secret_key(self) -> str | None:
        return self.CLERK_SECRET_KEY

    @property
    def clerk_jwt_key(self) -> str | None:
        return self.CLERK_JWT_KEY

    @property
    def clerk_publishable_key(self) -> str | None:
        return self.CLERK_PUBLISHABLE_KEY

    @property
    def clerk_authorized_parties(self) -> list[str]:
        if not self.CLERK_AUTHORIZED_PARTIES:
            return []
        return [p.strip() for p in self.CLERK_AUTHORIZED_PARTIES.split(",") if p.strip()]

    @property
    def is_clerk_configured(self) -> bool:
        return bool(self.CLERK_SECRET_KEY or self.CLERK_JWT_KEY)

    @property
    def desktop_mode(self) -> bool:
        return self.DESKTOP_MODE

    @property
    def desktop_backend_host(self) -> str:
        return self.DESKTOP_BACKEND_HOST

    @property
    def desktop_backend_port(self) -> int:
        return self.DESKTOP_BACKEND_PORT

    @property
    def app_data_dir(self) -> str | None:
        return self.APP_DATA_DIR


# Global settings singleton instance
settings = Settings()
