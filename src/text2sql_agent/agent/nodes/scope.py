"""select_schema_scope node — semantic search for candidate tables."""

import logging

from text2sql_agent.agent.state import AgentState
from text2sql_agent.config import settings
from text2sql_agent.rag.store import RAGStore

logger = logging.getLogger(__name__)

_store: RAGStore | None = None


def _get_store() -> RAGStore:
    global _store
    if _store is None:
        _store = RAGStore()
    return _store


async def select_schema_scope(state: AgentState) -> AgentState:
    """Search schema descriptions to identify candidate tables for the query.

    Sets state["candidate_tables"] with table names relevant to the question.
    """
    question = state["question"]
    store = _get_store()

    results = store.search_schemas(question, top_k=settings.rag_top_k)
    candidate_tables = [r.table_name for r in results]

    # Apply allowlist if configured
    allowlist = settings.table_allowlist_parsed
    if allowlist:
        candidate_tables = [
            t for t in candidate_tables if t in allowlist
        ]
        # Fallback to full allowlist if no intersection
        if not candidate_tables:
            candidate_tables = list(allowlist)

    # Take top 5 most relevant
    candidate_tables = candidate_tables[:5]

    logger.info(f"Candidate tables: {candidate_tables}")

    if not candidate_tables:
        return {
            "candidate_tables": [],
            "error": "No candidate tables identified for this question.",
            "response": "Không thể xác định bảng dữ liệu phù hợp cho câu hỏi này.",
        }

    return {"candidate_tables": candidate_tables}
