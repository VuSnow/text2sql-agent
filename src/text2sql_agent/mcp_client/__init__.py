"""MCP client package."""

from text2sql_agent.mcp_client.base import BaseMCPClient, BaseSQLMCPClient, MCPError
from text2sql_agent.mcp_client.factory import create_mcp_client, mcp_client_registry
from text2sql_agent.mcp_client.models import (
    ColumnInfo,
    Constraint,
    DryRunResult,
    Index,
    TableSchema,
)
from text2sql_agent.mcp_client.postgresql_client import PostgreSQLMCPClient

__all__ = [
    "BaseMCPClient",
    "BaseSQLMCPClient",
    "ColumnInfo",
    "Constraint",
    "DryRunResult",
    "Index",
    "MCPError",
    "PostgreSQLMCPClient",
    "TableSchema",
    "create_mcp_client",
    "mcp_client_registry",
]
