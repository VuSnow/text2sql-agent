"""retrieve_schema node — calls MCP to get DDL for candidate tables."""

import logging

from text2sql_agent.agent.state import AgentState
from text2sql_agent.config import settings
from text2sql_agent.mcp_client.factory import create_mcp_client
from text2sql_agent.policy import format_policy_context
from text2sql_agent.rag.store import RAGStore

logger = logging.getLogger(__name__)

_store: RAGStore | None = None


def _get_store() -> RAGStore:
    global _store
    if _store is None:
        _store = RAGStore()
    return _store


async def retrieve_schema(state: AgentState) -> AgentState:
    """Retrieve DDL and NL descriptions for candidate tables via MCP.

    Sets state["schema_context"] with formatted schema information.
    """
    candidate_tables = state.get("candidate_tables", [])
    if not candidate_tables:
        return {"schema_context": ""}

    mcp = create_mcp_client()
    store = _get_store()
    schema_parts = []

    for table_name in candidate_tables:
        try:
            # Get DDL from MCP
            table_schema = await mcp.get_table_schema(settings.schema_name, table_name)
            constraints = await mcp.get_constraints(settings.schema_name, table_name)

            # Format columns
            columns_text = "\n".join(
                f"    {col.column_name} {col.data_type}"
                f"{'' if col.is_nullable else ' NOT NULL'}"
                f"{' DEFAULT ' + col.column_default if col.column_default else ''}"
                for col in table_schema.columns
            )

            # Format constraints
            constraint_text = ""
            if constraints:
                constraint_lines = []
                for c in constraints:
                    if c.constraint_type_name == "PRIMARY KEY":
                        constraint_lines.append(f"    PRIMARY KEY ({', '.join(c.columns)})")
                    elif c.constraint_type_name == "FOREIGN KEY":
                        constraint_lines.append(
                            f"    FOREIGN KEY ({', '.join(c.columns)}) "
                            f"REFERENCES {c.foreign_table}({', '.join(c.foreign_columns)})"
                        )
                if constraint_lines:
                    constraint_text = "\n" + "\n".join(constraint_lines)

            # Get NL description from RAG store
            nl_description = ""
            schema_results = store.schema_collection.get(
                ids=[table_name], include=["metadatas"]
            )
            if schema_results["metadatas"]:
                nl_description = schema_results["metadatas"][0].get("description", "")

            schema_parts.append(
                f"-- Table: {table_name}\n"
                f"-- Description: {nl_description}\n"
                f"CREATE TABLE {table_name} (\n{columns_text}{constraint_text}\n);"
            )

        except Exception as e:
            logger.warning(f"Failed to retrieve schema for {table_name}: {e}")
            schema_parts.append(f"-- Table: {table_name} (schema unavailable: {e})")

    schema_context = "\n\n".join(schema_parts)
    policy_context = format_policy_context(candidate_tables)
    logger.info(f"Schema context: {len(candidate_tables)} tables, {len(schema_context)} chars")

    return {"schema_context": schema_context, "policy_context": policy_context}
