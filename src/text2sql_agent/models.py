"""Request/response Pydantic models for the Text2SQL API."""

from typing import Literal

from pydantic import BaseModel, Field


# ─── Request ─────────────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """Input for /query/preview and /query/execute endpoints."""

    question: str = Field(..., min_length=1, max_length=2000, description="Natural language question")
    execute: bool = Field(False, description="Whether to execute the generated SQL")
    clarification_response: str | None = Field(
        None,
        max_length=2000,
        description="User's answer to previous clarification questions",
    )


# ─── Response variants ───────────────────────────────────────────────────────


class QuerySuccess(BaseModel):
    """Successful SQL generation (and optional execution)."""

    status: Literal["success"] = "success"
    sql: str
    executed: bool = False
    results: list[dict] | None = None
    row_count: int | None = None
    warnings: list[str] | None = None
    steps: list[str] = Field(default_factory=list, description="Trace of nodes executed")


class NeedsClarification(BaseModel):
    """Agent needs more information from the user."""

    status: Literal["needs_clarification"] = "needs_clarification"
    original_question: str
    questions: list[str] = Field(..., description="1-3 clarification questions in Vietnamese")


class QueryBlocked(BaseModel):
    """Request was blocked by safety classification."""

    status: Literal["blocked"] = "blocked"
    reason: str
    block_type: str  # destructive | prompt_injection | raw_sql | unsupported


class QueryError(BaseModel):
    """Agent encountered an unrecoverable error."""

    status: Literal["error"] = "error"
    error: str
    error_type: str  # generation_failed | validation_failed | execution_failed | internal


# ─── Union response ──────────────────────────────────────────────────────────

QueryResponse = QuerySuccess | NeedsClarification | QueryBlocked | QueryError
