"""Agent state definition — shared TypedDict for all LangGraph nodes."""

from typing import TypedDict


class ClassificationResult(TypedDict):
    request_type: str  # data_query | explanation | unsafe | unsupported | ambiguous
    decision: str  # continue | clarify | block | explain
    requires_sql: bool
    flags: dict[str, bool]
    block_reason: str | None
    reason: str


class ValidationResult(TypedDict):
    valid: bool
    repairable: bool
    error_type: str | None  # syntax | missing_column | policy_violation | unknown
    error_message: str | None


class SemanticCheckIssue(TypedDict):
    type: str  # join_error | missing_filter | wrong_metric | wrong_grain | ...
    message: str
    evidence: str


class SemanticCheckResult(TypedDict):
    passed: bool
    severity: str  # info | warning | error
    issues: list[SemanticCheckIssue]
    repair_instruction: str | None
    suggestion: str | None


class AgentState(TypedDict, total=False):
    """Full agent state passed between LangGraph nodes."""

    # Input
    question: str
    execute: bool

    # Classification
    classification: ClassificationResult

    # Clarification
    clarification_questions: list[str]

    # Schema scope
    candidate_tables: list[str]
    schema_context: str  # DDL + NL descriptions for candidate tables
    policy_context: str  # policy rules for the query scope

    # RAG examples
    example_context: str  # formatted similar SQL examples

    # SQL generation
    generated_sql: str

    # Validation
    validation_result: ValidationResult

    # Semantic check
    semantic_check: SemanticCheckResult

    # Repair
    repair_attempts: int

    # Execution
    query_results: list[dict]

    # Final response
    response: str
    error: str | None
