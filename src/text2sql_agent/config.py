from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class LLMProvider(str, Enum):
    OPENAI = "openai"
    BEDROCK = "bedrock"


class EmbeddingProvider(str, Enum):
    BEDROCK = "bedrock"
    OPENAI = "openai"


class Settings(BaseSettings):
    # ─── MCP Server ──────────────────────────────────────────────────────────

    mcp_backend: str = Field(
        "postgresql",
        alias="MCP_BACKEND",
        description="Backend type for MCP server.",
    )

    postgresql_mcp_server_url: str = Field(
        "http://localhost:8000/mcp",
        alias="POSTGRESQL_MCP_SERVER_URL",
        description="URL of the PostgreSQL MCP server.",
    )

    # ─── LLM ─────────────────────────────────────────────────────────────────

    llm_provider: LLMProvider = Field(
        LLMProvider.OPENAI,
        alias="LLM_PROVIDER",
        description="LLM provider: 'openai' or 'bedrock'.",
    )

    llm_model: str = Field(
        "gpt-4o-mini",
        alias="LLM_MODEL",
        description="Model identifier for the LLM.",
    )

    llm_api_key: str = Field(
        "",
        alias="LLM_API_KEY",
        description="API key for the LLM provider.",
    )

    llm_temperature: float = Field(
        0.0,
        alias="LLM_TEMPERATURE",
        description="Temperature for LLM generation.",
    )

    # ─── AWS Bedrock ─────────────────────────────────────────────────────────

    aws_region: str = Field(
        "us-east-1",
        alias="AWS_REGION",
        description="AWS region for Bedrock.",
    )

    aws_profile: Optional[str] = Field(
        "btc-bedrock",
        alias="AWS_PROFILE",
        description="AWS profile name for Bedrock credentials.",
    )

    # ─── Embedding ───────────────────────────────────────────────────────────

    embedding_provider: EmbeddingProvider = Field(
        EmbeddingProvider.BEDROCK,
        alias="EMBEDDING_PROVIDER",
        description="Embedding provider: 'bedrock' or 'openai'.",
    )

    embedding_model_id: str = Field(
        "amazon.titan-embed-text-v2:0",
        alias="EMBEDDING_MODEL_ID",
        description="Model ID for text embeddings (Bedrock: amazon.titan-embed-text-v2:0, OpenAI: text-embedding-3-small).",
    )

    embedding_dimensions: int = Field(
        1024,
        alias="EMBEDDING_DIMENSIONS",
        description="Dimensionality of embedding vectors.",
    )

    # ─── Reranker ────────────────────────────────────────────────────────────

    reranker_enabled: bool = Field(
        False,
        alias="RERANKER_ENABLED",
        description="Enable reranking of retrieval results.",
    )

    reranker_model_id: str = Field(
        "cohere.rerank-v3-5:0",
        alias="RERANKER_MODEL_ID",
        description="Model ID for the reranker.",
    )

    reranker_top_k: int = Field(
        5,
        alias="RERANKER_TOP_K",
        description="Number of top results after reranking.",
    )

    # ─── ChromaDB ────────────────────────────────────────────────────────────

    chroma_persist_dir: Path = Field(
        Path("./data/chroma"),
        alias="CHROMA_PERSIST_DIR",
        description="Directory for ChromaDB persistence.",
    )

    # ─── RAG ─────────────────────────────────────────────────────────────────

    rag_top_k: int = Field(
        10,
        alias="RAG_TOP_K",
        description="Initial retrieval count before reranking.",
    )

    rag_schema_collection: str = Field(
        "schema_descriptions",
        alias="RAG_SCHEMA_COLLECTION",
        description="ChromaDB collection name for schema descriptions.",
    )

    rag_examples_collection: str = Field(
        "sql_examples",
        alias="RAG_EXAMPLES_COLLECTION",
        description="ChromaDB collection name for SQL examples.",
    )

    # ─── Agent Behavior ──────────────────────────────────────────────────────

    max_repair_attempts: int = Field(
        3,
        alias="MAX_REPAIR_ATTEMPTS",
        description="Max attempts to repair a failed SQL query.",
    )

    default_execute: bool = Field(
        False,
        alias="DEFAULT_EXECUTE",
        description="Whether to execute queries by default.",
    )

    # ─── Schema Scope ────────────────────────────────────────────────────────

    table_allowlist: list[str] = Field(
        default_factory=list,
        alias="TABLE_ALLOWLIST",
        description="Comma-separated list of allowed tables.",
    )

    schema_name: str = Field(
        "public",
        alias="SCHEMA_NAME",
        description="Database schema name.",
    )

    # ─── Logging ─────────────────────────────────────────────────────────────

    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
