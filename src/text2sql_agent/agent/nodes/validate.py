"""validate_sql node — MCP dry_run + error classification."""

import logging

from text2sql_agent.agent.state import AgentState
from text2sql_agent.config import settings
from text2sql_agent.mcp_client.base import MCPError
from text2sql_agent.mcp_client.factory import create_mcp_client

logger = logging.getLogger(__name__)


def _classify_error(error_msg: str) -> tuple[str, bool]:
    """Classify SQL validation error into type and repairability.

    Returns (error_type, repairable).
    """
    error_lower = error_msg.lower()

    if "permission denied" in error_lower or "access" in error_lower:
        return "policy_violation", False

    if "does not exist" in error_lower:
        return "missing_column", True

    if "syntax error" in error_lower:
        return "syntax", True

    if "ambiguous" in error_lower:
        return "missing_column", True

    if "division by zero" in error_lower:
        return "syntax", True

    return "unknown", True


async def validate_sql(state: AgentState) -> AgentState:
    """Validate generated SQL via MCP dry_run.

    Sets state["validation_result"] with valid, repairable, error_type, error_message.
    """
    sql = state.get("generated_sql", "")
    if not sql:
        return {
            "validation_result": {
                "valid": False,
                "repairable": False,
                "error_type": "unknown",
                "error_message": "No SQL generated",
            }
        }

    mcp = create_mcp_client()

    try:
        result = await mcp.dry_run_query(sql)

        if result.valid:
            logger.info("SQL validation passed")
            return {
                "validation_result": {
                    "valid": True,
                    "repairable": False,
                    "error_type": None,
                    "error_message": None,
                }
            }
        else:
            error_msg = result.error or result.message
            error_type, repairable = _classify_error(error_msg)
            logger.warning(f"SQL validation failed: [{error_type}] {error_msg}")
            return {
                "validation_result": {
                    "valid": False,
                    "repairable": repairable,
                    "error_type": error_type,
                    "error_message": error_msg,
                }
            }

    except MCPError as e:
        error_msg = str(e)
        error_type, repairable = _classify_error(error_msg)
        logger.error(f"MCP error during validation: {error_msg}")
        return {
            "validation_result": {
                "valid": False,
                "repairable": repairable,
                "error_type": error_type,
                "error_message": error_msg,
            }
        }
