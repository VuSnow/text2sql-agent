"""Abstract bases for MCP clients."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from text2sql_agent.mcp_client.models import (
    Constraint,
    DryRunResult,
    Index,
    TableSchema,
)

logger = logging.getLogger(__name__)

# Transient errors that should trigger automatic retry
RETRYABLE_EXCEPTIONS = (ConnectionError, OSError, TimeoutError)


class MCPError(Exception):
    """Error returned by MCP server tool."""
    pass


class BaseMCPClient(ABC):
    """Transport-only base with built-in retry for transient failures.

    Subclasses implement `_call_tool_raw()` for the wire protocol.
    The retry logic lives here so all implementations get it for free.
    """

    def __init__(self, server_url: str):
        self.server_url = server_url

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        reraise=True,
    )
    async def _call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool with automatic retry on transient failures.

        Retries up to 3 times with exponential backoff for
        ConnectionError, OSError, TimeoutError.

        Delegates actual transport to `_call_tool_raw()`.
        """
        return await self._call_tool_raw(tool_name, arguments)

    @abstractmethod
    async def _call_tool_raw(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Execute the MCP tool call via the underlying transport.

        Should return the parsed result value.
        Should raise MCPError for non-transient server errors.
        Should let ConnectionError/OSError/TimeoutError propagate for retry.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if MCP server is reachable."""
        ...


class BaseSQLMCPClient(BaseMCPClient):
    """Common SQL interface that agent nodes program against.

    Subclasses (PostgreSQL, BigQuery, etc.) map these to their
    MCP server's specific tool names.
    """

    @abstractmethod
    async def list_schemas(self) -> list[str]:
        """List available schemas/datasets."""
        ...

    @abstractmethod
    async def list_tables(self, schema: str) -> list[str]:
        """List tables in a schema/dataset."""
        ...

    @abstractmethod
    async def get_table_schema(self, schema: str, table: str) -> TableSchema:
        """Get column definitions for a table."""
        ...

    @abstractmethod
    async def get_constraints(self, schema: str, table: str) -> list[Constraint]:
        """Get primary/foreign key constraints."""
        ...

    @abstractmethod
    async def get_indexes(self, schema: str, table: str) -> list[Index]:
        """Get index information for a table."""
        ...

    @abstractmethod
    async def get_column_values(
        self, schema: str, table: str, column: str, limit: int = 50
    ) -> list[str]:
        """Get distinct non-null values for a column.

        Useful for understanding cardinality and valid filter values.
        """
        ...

    @abstractmethod
    async def dry_run_query(self, sql: str) -> DryRunResult:
        """Validate SQL without executing (syntax + plan check)."""
        ...

    @abstractmethod
    async def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL query and return rows."""
        ...

    @abstractmethod
    async def explain_query(self, sql: str) -> str:
        """Get query execution plan."""
        ...
