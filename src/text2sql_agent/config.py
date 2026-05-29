from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    OPENAI = "openai"


class Settings(BaseSettings):
    # MCP Server
    mcp_backend: str = "postgresql"
    postgresql_mcp_server_url: str = "http://localhost:8000"

    # LLM
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_temperature: float = 0.0

    # ChromaDB
    chroma_persist_dir: Path = Path("./data/chroma")

    # RAG
    rag_top_k: int = 5

    # Agent behavior
    max_repair_attempts: int = 3
    default_execute: bool = False

    # Schema scope
    table_allowlist: list[str] = []
    schema_name: str = "public"

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
