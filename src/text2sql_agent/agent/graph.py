"""LangGraph agent assembly — wires nodes into a compiled StateGraph."""

import logging

from langgraph.graph import END, StateGraph

from text2sql_agent.agent.nodes import (
    clarify_question,
    classify_request,
    generate_sql,
    maybe_execute,
    repair_sql,
    retrieve_examples,
    retrieve_schema,
    select_schema_scope,
    semantic_check_sql,
    validate_sql,
)
from text2sql_agent.agent.state import AgentState
from text2sql_agent.config import settings

logger = logging.getLogger(__name__)


# ─── Routing functions ────────────────────────────────────────────────────────


def route_after_classify(state: AgentState) -> str:
    """Route based on classification decision."""
    classification = state.get("classification", {})
    decision = classification.get("decision", "block")

    if decision == "continue":
        return "select_schema_scope"
    elif decision == "clarify":
        return "clarify_question"
    else:
        # block, explain, or unknown → end
        return END


def route_after_validate(state: AgentState) -> str:
    """Route based on SQL validation result."""
    validation = state.get("validation_result", {})

    if validation.get("valid"):
        return "semantic_check_sql"

    # Check if repairable and within attempt limit
    if validation.get("repairable") and state.get("repair_attempts", 0) < settings.max_repair_attempts:
        return "repair_sql"

    # Not repairable or max attempts reached → end with error
    return END


def route_after_semantic_check(state: AgentState) -> str:
    """Route based on semantic check result."""
    check = state.get("semantic_check", {})
    severity = check.get("severity", "info")

    if check.get("passed") or severity in ("info", "warning"):
        return "maybe_execute"

    # severity == "error" → try repair
    if state.get("repair_attempts", 0) < settings.max_repair_attempts:
        return "repair_sql"

    # Max attempts reached
    return END


def route_after_repair(state: AgentState) -> str:
    """After repair, always go back to validate."""
    return "validate_sql"


# ─── Graph builder ────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build the Text2SQL agent StateGraph (uncompiled)."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify_request", classify_request)
    graph.add_node("clarify_question", clarify_question)
    graph.add_node("select_schema_scope", select_schema_scope)
    graph.add_node("retrieve_schema", retrieve_schema)
    graph.add_node("retrieve_examples", retrieve_examples)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("validate_sql", validate_sql)
    graph.add_node("semantic_check_sql", semantic_check_sql)
    graph.add_node("repair_sql", repair_sql)
    graph.add_node("maybe_execute", maybe_execute)

    # Entry point
    graph.set_entry_point("classify_request")

    # Conditional edges
    graph.add_conditional_edges(
        "classify_request",
        route_after_classify,
        {
            "select_schema_scope": "select_schema_scope",
            "clarify_question": "clarify_question",
            END: END,
        },
    )

    # Clarify → END (return questions to user)
    graph.add_edge("clarify_question", END)

    # Linear chain: scope → schema → examples → generate → validate
    graph.add_edge("select_schema_scope", "retrieve_schema")
    graph.add_edge("retrieve_schema", "retrieve_examples")
    graph.add_edge("retrieve_examples", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")

    # Validate → conditional
    graph.add_conditional_edges(
        "validate_sql",
        route_after_validate,
        {
            "semantic_check_sql": "semantic_check_sql",
            "repair_sql": "repair_sql",
            END: END,
        },
    )

    # Semantic check → conditional
    graph.add_conditional_edges(
        "semantic_check_sql",
        route_after_semantic_check,
        {
            "maybe_execute": "maybe_execute",
            "repair_sql": "repair_sql",
            END: END,
        },
    )

    # Repair → back to validate
    graph.add_edge("repair_sql", "validate_sql")

    # Execute → END
    graph.add_edge("maybe_execute", END)

    return graph


def create_agent():
    """Create and compile the Text2SQL agent graph."""
    graph = build_graph()
    return graph.compile()
