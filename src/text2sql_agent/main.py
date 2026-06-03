import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from text2sql_agent.agent.graph import create_agent
from text2sql_agent.config import settings
from text2sql_agent.mcp_client import create_mcp_client
from text2sql_agent.models import (
    NeedsClarification,
    QueryBlocked,
    QueryError,
    QueryRequest,
    QueryResponse,
    QuerySuccess,
)

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("text2sql_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting text2sql-agent (model=%s)", settings.llm_model)
    yield


app = FastAPI(title="text2sql-agent", version="0.1.0", lifespan=lifespan)
mcp_client = create_mcp_client()
agent = create_agent()


@app.get("/health")
async def health() -> dict[str, str | bool]:
    mcp_ok = await mcp_client.health_check()
    return {
        "status": "ok" if mcp_ok else "degraded",
        "mcp_server": settings.postgresql_mcp_server_url,
        "mcp_connected": mcp_ok,
    }


# ─── Helper: run agent and parse result ──────────────────────────────────────


async def _run_agent(request: QueryRequest, execute: bool) -> QueryResponse:
    """Run the agent graph and map final state to a response model."""
    question = request.question
    if request.clarification_response:
        question = f"{request.question}\n\nClarification: {request.clarification_response}"

    input_state = {"question": question, "execute": execute}

    try:
        final_state = await agent.ainvoke(input_state)
    except Exception as e:
        logger.exception("Agent invocation failed")
        return QueryError(error=str(e), error_type="internal")

    return _state_to_response(final_state, question)


def _state_to_response(state: dict[str, Any], original_question: str) -> QueryResponse:
    """Map agent final state to the appropriate response model."""
    classification = state.get("classification", {})
    decision = classification.get("decision", "")

    # Blocked
    if decision == "block":
        return QueryBlocked(
            reason=classification.get("reason", "Request blocked"),
            block_type=classification.get("block_reason", "unsupported"),
        )

    # Needs clarification
    clarification_questions = state.get("clarification_questions")
    if clarification_questions:
        return NeedsClarification(
            original_question=original_question,
            questions=clarification_questions,
        )

    # Error (no SQL generated or validation failed permanently)
    error = state.get("error")
    generated_sql = state.get("generated_sql")
    if not generated_sql:
        return QueryError(
            error=error or "No SQL generated",
            error_type="generation_failed",
        )

    validation = state.get("validation_result", {})
    if validation and not validation.get("valid") and not state.get("query_results"):
        return QueryError(
            error=validation.get("error_message", error or "Validation failed"),
            error_type="validation_failed",
        )

    # Success
    warnings = []
    semantic = state.get("semantic_check", {})
    if semantic.get("severity") == "warning":
        issues = semantic.get("issues", [])
        for issue in issues:
            if isinstance(issue, dict):
                warnings.append(issue.get("message", ""))
            else:
                warnings.append(str(issue))

    query_results = state.get("query_results")
    executed = query_results is not None

    return QuerySuccess(
        sql=generated_sql,
        executed=executed,
        results=query_results if executed else None,
        row_count=len(query_results) if executed and query_results else None,
        warnings=warnings or None,
        steps=_extract_steps(state),
    )


def _extract_steps(state: dict[str, Any]) -> list[str]:
    """Extract a trace of which processing steps were applied."""
    steps = ["classify_request"]
    if state.get("clarification_questions"):
        steps.append("clarify_question")
        return steps
    if state.get("candidate_tables"):
        steps.append("select_schema_scope")
        steps.append("retrieve_schema")
    if state.get("example_context"):
        steps.append("retrieve_examples")
    if state.get("generated_sql"):
        steps.append("generate_sql")
    if state.get("validation_result"):
        steps.append("validate_sql")
    repair_attempts = state.get("repair_attempts", 0)
    if repair_attempts > 0:
        steps.extend(["repair_sql"] * repair_attempts)
    if state.get("semantic_check"):
        steps.append("semantic_check_sql")
    if state.get("query_results") is not None:
        steps.append("maybe_execute")
    return steps


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.post("/query/preview", response_model=QueryResponse)
async def query_preview(request: QueryRequest) -> QueryResponse:
    """Generate and validate SQL without executing."""
    return await _run_agent(request, execute=False)


@app.post("/query/execute", response_model=QueryResponse)
async def query_execute(request: QueryRequest) -> QueryResponse:
    """Generate, validate, and execute SQL."""
    return await _run_agent(request, execute=True)


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream agent execution steps via SSE."""
    question = request.question
    if request.clarification_response:
        question = f"{request.question}\n\nClarification: {request.clarification_response}"

    input_state = {"question": question, "execute": request.execute}

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        try:
            async for event in agent.astream_events(input_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name != "LangGraph":
                    yield {"event": "step_start", "data": name}
                elif kind == "on_chain_end" and name != "LangGraph":
                    yield {"event": "step_end", "data": name}
                elif kind == "on_chain_end" and name == "LangGraph":
                    # Final state
                    output = event.get("data", {}).get("output", {})
                    response = _state_to_response(output, question)
                    yield {"event": "result", "data": response.model_dump_json()}
        except Exception as e:
            logger.exception("Stream error")
            error = QueryError(error=str(e), error_type="internal")
            yield {"event": "error", "data": error.model_dump_json()}

    return EventSourceResponse(event_generator())


# ─── Error handling ──────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": "Internal server error", "error_type": "internal"},
    )

