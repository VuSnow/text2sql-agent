"""PostgreSQL MCP client — concrete implementation using FastMCP."""

import json
import logging
import re
from typing import Any

from fastmcp import Client

from text2sql_agent.config import settings
from text2sql_agent.mcp_client.base import BaseSQLMCPClient, MCPError
from text2sql_agent.mcp_client.factory import mcp_client_registry
from text2sql_agent.mcp_client.models import (
    ColumnInfo,
    Constraint,
    DryRunResult,
    Index,
    TableSchema,
)

logger = logging.getLogger(__name__)


@mcp_client_registry.register("postgresql")
class PostgreSQLMCPClient(BaseSQLMCPClient):
    """Connects to postgresql-mcp-server via FastMCP Streamable HTTP."""

    def __init__(self, server_url: str | None = None):
        url = server_url or settings.postgresql_mcp_server_url
        super().__init__(server_url=url)
        self._client = Client(self.server_url)

    async def _call_tool_raw(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call MCP tool, parse JSON response, raise MCPError on failure.

        Lets ConnectionError/OSError/TimeoutError propagate for base retry.
        """
        try:
            async with self._client:
                result = await self._client.call_tool(tool_name, arguments or {})
        except (ConnectionError, OSError, TimeoutError):
            raise  # Let base class retry these
        except Exception as e:
            raise MCPError(f"MCP connection failed: {e}") from e

        content = getattr(result, "content", None) or []
        if not content:
            raise MCPError(f"Empty response from tool '{tool_name}'")

        text_parts = [item.text for item in content if hasattr(item, "text") and item.text is not None]
        if not text_parts:
            raise MCPError(f"Tool '{tool_name}' returned no text content")

        text = "\n".join(text_parts)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text  # Return raw text if not JSON

        if "error" in parsed:
            raise MCPError(f"Tool '{tool_name}' error: {parsed['error']}")

        return parsed.get("result", parsed)

    async def health_check(self) -> bool:
        """Verify MCP server connectivity by listing tools."""
        try:
            async with self._client:
                tools = await self._client.list_tools()
            return len(tools) > 0
        except Exception:
            return False

    # --- BaseSQLMCPClient interface implementation ---

    async def list_schemas(self) -> list[str]:
        result = await self._call_tool("list_schemas")
        return self._parse_bullet_list(result)

    async def list_tables(self, schema: str) -> list[str]:
        result = await self._call_tool("list_tables", {"schema": schema})
        return self._parse_table_list(result)

    async def get_table_schema(self, schema: str, table: str) -> TableSchema:
        result = await self._call_tool("get_table_schema", {"schema": schema, "table_name": table})
        return self._parse_table_schema(result, schema=schema, table=table)

    async def get_constraints(self, schema: str, table: str) -> list[Constraint]:
        result = await self._call_tool("get_constraints", {"schema": schema, "table_name": table})
        return self._parse_constraints(result)

    async def get_indexes(self, schema: str, table: str) -> list[Index]:
        result = await self._call_tool("get_indexes", {"schema": schema, "table_name": table})
        return self._parse_indexes(result)

    async def get_column_values(
        self, schema: str, table: str, column: str, limit: int = 50
    ) -> list[str]:
        result = await self._call_tool(
            "get_column_values",
            {"schema": schema, "table_name": table, "column": column, "limit": limit},
        )
        return self._parse_bullet_list(result)

    async def dry_run_query(self, sql: str) -> DryRunResult:
        result = await self._call_tool("dry_run_query", {"query": sql})
        return self._parse_dry_run_result(result)

    async def execute_query(self, sql: str) -> list[dict[str, Any]]:
        result = await self._call_tool("execute_query", {"query": sql})
        return self._parse_query_results(result)

    async def explain_query(self, sql: str) -> str:
        result = await self._call_tool("explain_query", {"query": sql})
        return str(result)

    @staticmethod
    def _parse_bullet_list(result: Any) -> list[str]:
        if isinstance(result, list):
            return [str(item) for item in result]
        text = str(result)
        items: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("• "):
                items.append(stripped.removeprefix("• ").strip())
        return items

    @staticmethod
    def _parse_table_list(result: Any) -> list[str]:
        if isinstance(result, list):
            if all(isinstance(item, str) for item in result):
                return [str(item) for item in result]
            if all(isinstance(item, dict) and "table_name" in item for item in result):
                return [str(item["table_name"]) for item in result]
        text = str(result)
        tables: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("Tables in", "Table", "-", "Total:")):
                continue
            parts = re.split(r"\s{2,}", stripped, maxsplit=2)
            if parts:
                tables.append(parts[0])
        return tables

    @staticmethod
    def _parse_table_schema(result: Any, schema: str, table: str) -> TableSchema:
        if isinstance(result, dict):
            if "columns" in result:
                return TableSchema(
                    schema_name=result.get("schema", schema),
                    table=result.get("table", table),
                    columns=[ColumnInfo(**col) for col in result["columns"]],
                )
        text = str(result)
        columns: list[ColumnInfo] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("Columns for", "#", "-", "Total:")):
                continue
            parts = re.split(r"\s{2,}", stripped, maxsplit=4)
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            columns.append(ColumnInfo(
                ordinal_position=int(parts[0]),
                column_name=parts[1],
                data_type=parts[2],
                is_nullable=parts[3] == "YES",
                column_default=parts[4] if len(parts) > 4 and parts[4] else None,
            ))
        return TableSchema(schema_name=schema, table=table, columns=columns)

    @staticmethod
    def _parse_indexes(result: Any) -> list[Index]:
        if isinstance(result, list):
            return [Index(**item) for item in result]
        text = str(result)
        indexes: list[Index] = []
        current: dict[str, Any] | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("Indexes for", "Total:")):
                continue
            if stripped.startswith("• "):
                if current is not None:
                    indexes.append(Index(**current))
                name_part = stripped.removeprefix("• ").strip()
                flags_match = re.match(r"^(?P<name>.+?)(?: \[(?P<flags>.+)\])?$", name_part)
                flags = [flag.strip() for flag in (flags_match.group("flags") or "").split(",") if flag.strip()]
                current = {
                    "index_name": flags_match.group("name"),
                    "is_primary": "PRIMARY" in flags,
                    "is_unique": "UNIQUE" in flags,
                    "index_type": None,
                    "columns": [],
                }
                continue
            if current is None:
                continue
            type_match = re.match(r"^Type: (?P<index_type>[^,]+), Columns: \((?P<columns>.*)\)$", stripped)
            if type_match:
                columns = [column.strip() for column in type_match.group("columns").split(",") if column.strip()]
                current["index_type"] = type_match.group("index_type")
                current["columns"] = columns
        if current is not None:
            indexes.append(Index(**current))
        return indexes

    @staticmethod
    def _parse_constraints(result: Any) -> list[Constraint]:
        if isinstance(result, list):
            return [Constraint(**item) for item in result]
        text = str(result)
        constraints: list[Constraint] = []
        current: dict[str, Any] | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("Constraints for", "Total:")):
                continue
            if stripped.startswith("• "):
                if current is not None:
                    constraints.append(Constraint(**current))
                match = re.match(r"^• (?P<name>.+) \((?P<type>.+)\)$", stripped)
                if match is None:
                    continue
                current = {
                    "constraint_name": match.group("name"),
                    "constraint_type_name": match.group("type"),
                    "columns": [],
                    "foreign_schema": None,
                    "foreign_table": None,
                    "foreign_columns": [],
                }
                continue
            if current is None:
                continue
            columns_match = re.match(r"^Columns: \((?P<columns>.*)\)$", stripped)
            if columns_match:
                current["columns"] = [column.strip() for column in columns_match.group("columns").split(",") if column.strip()]
                continue
            references_match = re.match(
                r"^References: (?P<schema>[^.]+)\.(?P<table>[^ ]+) \((?P<columns>.*)\)$",
                stripped,
            )
            if references_match:
                current["foreign_schema"] = references_match.group("schema")
                current["foreign_table"] = references_match.group("table")
                current["foreign_columns"] = [
                    column.strip() for column in references_match.group("columns").split(",") if column.strip()
                ]
        if current is not None:
            constraints.append(Constraint(**current))
        return constraints

    @staticmethod
    def _parse_dry_run_result(result: Any) -> DryRunResult:
        if isinstance(result, dict):
            return DryRunResult(**result)
        text = str(result)
        if text.startswith("Query is valid"):
            return DryRunResult(valid=True, message=text, error=None)
        if text.startswith("Query rejected:"):
            return DryRunResult(valid=False, message=text, error=text.removeprefix("Query rejected:").strip())
        if text.startswith("Query blocked:"):
            return DryRunResult(valid=False, message=text, error=text.removeprefix("Query blocked:").strip())
        return DryRunResult(valid=False, message=text, error=text)

    def _parse_query_results(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return result
        text = str(result)
        if text.startswith("Query returned 0 rows"):
            return []

        lines = [line for line in text.splitlines() if line]
        if len(lines) < 4 or not lines[0].startswith("Results:"):
            raise MCPError(f"Unexpected execute_query result format: {text}")

        columns = [column.strip() for column in lines[1].split(" | ")]
        rows: list[dict[str, Any]] = []
        for line in lines[3:]:
            if line.startswith("... and "):
                break
            values = [value.strip() for value in line.split(" | ")]
            if len(values) != len(columns):
                raise MCPError(f"Unexpected row format in execute_query result: {line}")
            rows.append({column: self._coerce_scalar(value) for column, value in zip(columns, values, strict=True)})
        return rows

    @staticmethod
    def _coerce_scalar(value: str) -> Any:
        if value == "NULL":
            return None
        if value in {"True", "False"}:
            return value == "True"
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
        return value
