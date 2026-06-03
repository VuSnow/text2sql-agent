"""retrieve_examples node — searches similar SQL examples from RAG store."""

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


async def retrieve_examples(state: AgentState) -> AgentState:
    """Retrieve similar SQL examples filtered by candidate tables.

    Sets state["example_context"] with formatted examples for the LLM.
    """
    question = state["question"]
    candidate_tables = state.get("candidate_tables", [])
    store = _get_store()

    results = store.search_examples(
        query=question,
        table_filter=candidate_tables if candidate_tables else None,
        top_k=settings.reranker_top_k,
    )

    if not results:
        # Fallback: search without table filter
        results = store.search_examples(query=question, top_k=3)

    # Format examples for LLM context
    example_parts = []
    for i, r in enumerate(results, 1):
        example_parts.append(
            f"Example {i}:\n"
            f"  Question: {r.question}\n"
            f"  Tables: {', '.join(r.tables)}\n"
            f"  SQL:\n    {r.sql}\n"
            f"  Explanation: {r.explanation}"
        )

    example_context = "\n\n".join(example_parts)
    logger.info(f"Retrieved {len(results)} examples")

    return {"example_context": example_context}
