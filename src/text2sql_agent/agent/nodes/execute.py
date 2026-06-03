"""maybe_execute node — executes validated SQL if execute flag is set."""

import logging

from text2sql_agent.agent.state import AgentState
from text2sql_agent.config import settings
from text2sql_agent.mcp_client.base import MCPError
from text2sql_agent.mcp_client.factory import create_mcp_client

logger = logging.getLogger(__name__)


async def maybe_execute(state: AgentState) -> AgentState:
    """Execute the SQL query if execute flag is enabled.

    Sets state["query_results"] and state["response"].
    """
    sql = state.get("generated_sql", "")
    execute = state.get("execute", settings.default_execute)

    if not execute:
        # Return SQL as the response without executing
        response = f"```sql\n{sql}\n```"
        logger.info("Execution skipped (execute=False)")
        return {"response": response, "query_results": None}

    mcp = create_mcp_client()

    try:
        results = await mcp.execute_query(sql)
        logger.info(f"Query executed: {len(results)} rows")

        # Format response
        if not results:
            response = f"```sql\n{sql}\n```\n\nKết quả: Không có dữ liệu phù hợp."
        else:
            # Format as markdown table
            headers = list(results[0].keys())
            header_row = "| " + " | ".join(headers) + " |"
            separator = "| " + " | ".join("---" for _ in headers) + " |"
            data_rows = []
            for row in results[:50]:  # Limit display to 50 rows
                data_rows.append(
                    "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |"
                )

            table = "\n".join([header_row, separator] + data_rows)
            row_note = (
                f"\n\n_Hiển thị {min(len(results), 50)}/{len(results)} dòng._"
                if len(results) > 50
                else ""
            )
            response = f"```sql\n{sql}\n```\n\n{table}{row_note}"

        return {"query_results": results, "response": response}

    except MCPError as e:
        error_msg = str(e)
        logger.error(f"Query execution failed: {error_msg}")
        return {
            "query_results": None,
            "error": error_msg,
            "response": f"```sql\n{sql}\n```\n\nLỗi khi thực thi: {error_msg}",
        }
