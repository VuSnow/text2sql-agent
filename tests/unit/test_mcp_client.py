"""Unit tests for PostgreSQLMCPClient with mocked FastMCP Client."""

from contextlib import contextmanager
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from text2sql_agent.mcp_client import PostgreSQLMCPClient, MCPError
from text2sql_agent.mcp_client.models import ColumnInfo, DryRunResult, TableSchema


@pytest.fixture
def client():
    return PostgreSQLMCPClient(server_url="http://localhost:9999")


def _make_tool_result(data) -> MagicMock:
    """Create a mock CallToolResult with JSON text content."""
    content_item = MagicMock()
    content_item.text = json.dumps({"result": data})
    result = MagicMock()
    result.content = [content_item]
    return result


def _make_error_result(error_msg: str) -> MagicMock:
    content_item = MagicMock()
    content_item.text = json.dumps({"error": error_msg})
    result = MagicMock()
    result.content = [content_item]
    return result


@contextmanager
def _mock_client_context(client, call_tool_return=None, list_tools_return=None):
    """Patch the FastMCP Client to avoid real connections."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    if call_tool_return is not None:
        mock.call_tool = AsyncMock(return_value=call_tool_return)
    if list_tools_return is not None:
        mock.list_tools = AsyncMock(return_value=list_tools_return)
    with patch.object(client, "_client", mock):
        yield mock


def _server_text_result(text: str) -> MagicMock:
    return _make_tool_result(text)


@pytest.mark.asyncio
async def test_call_tool_success(client):
    mock_result = _make_tool_result(["public", "analytics"])

    with _mock_client_context(client, call_tool_return=mock_result):
        result = await client._call_tool("list_schemas")

    assert result == ["public", "analytics"]


@pytest.mark.asyncio
async def test_call_tool_error_response(client):
    mock_result = _make_error_result("permission denied")

    with _mock_client_context(client, call_tool_return=mock_result):
        with pytest.raises(MCPError, match="permission denied"):
            await client._call_tool("execute_query", {"sql": "SELECT 1"})


@pytest.mark.asyncio
async def test_call_tool_connection_failure_retries_then_raises(client):
    """ConnectionError triggers retry; after 3 attempts it re-raises."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
    mock.__aexit__ = AsyncMock(return_value=False)
    with patch.object(client, "_client", mock):
        with pytest.raises(ConnectionError, match="refused"):
            await client._call_tool("list_schemas")
    # Verify it attempted 3 times (tenacity stop_after_attempt=3)
    assert mock.__aenter__.call_count == 3


@pytest.mark.asyncio
async def test_call_tool_non_retryable_error(client):
    """Non-transient errors raise MCPError immediately without retry."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(side_effect=RuntimeError("unexpected"))
    mock.__aexit__ = AsyncMock(return_value=False)
    with patch.object(client, "_client", mock):
        with pytest.raises(MCPError, match="MCP connection failed"):
            await client._call_tool("list_schemas")
    assert mock.__aenter__.call_count == 1


@pytest.mark.asyncio
async def test_call_tool_empty_content(client):
    mock_result = MagicMock()
    mock_result.content = []

    with _mock_client_context(client, call_tool_return=mock_result):
        with pytest.raises(MCPError, match="Empty response"):
            await client._call_tool("list_schemas")


@pytest.mark.asyncio
async def test_health_check_success(client):
    with _mock_client_context(client, list_tools_return=[MagicMock(), MagicMock()]):
        assert await client.health_check() is True


@pytest.mark.asyncio
async def test_health_check_failure(client):
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
    mock.__aexit__ = AsyncMock(return_value=False)
    with patch.object(client, "_client", mock):
        assert await client.health_check() is False


@pytest.mark.asyncio
async def test_list_tables(client):
    mock_result = _server_text_result(
        "Tables in 'public':\n\n"
        "Table                                    Type            Est. Rows   \n"
        "-------------------------------------------------------------------\n"
        "customers                                BASE TABLE      10\n"
        "transactions                             BASE TABLE      150\n"
        "\nTotal: 2 table(s)"
    )

    with _mock_client_context(client, call_tool_return=mock_result) as mock_client:
        tables = await client.list_tables("public")

    assert tables == ["customers", "transactions"]
    mock_client.call_tool.assert_awaited_once_with("list_tables", {"schema": "public"})


@pytest.mark.asyncio
async def test_get_table_schema(client):
    mock_result = _server_text_result(
        "Columns for 'public.customers':\n\n"
        "#    Column                         Type                 Nullable   Default\n"
        "------------------------------------------------------------------------------------------\n"
        "1    id                             bigint               NO         \n"
        "2    email                          varchar(255)         YES        \n"
        "\nTotal: 2 column(s)"
    )

    with _mock_client_context(client, call_tool_return=mock_result) as mock_client:
        result = await client.get_table_schema("public", "customers")

    assert isinstance(result, TableSchema)
    assert result.schema_name == "public"
    assert result.table == "customers"
    assert len(result.columns) == 2
    assert result.columns[0] == ColumnInfo(
        ordinal_position=1,
        column_name="id",
        data_type="bigint",
        is_nullable=False,
        column_default=None,
    )
    assert result.columns[1] == ColumnInfo(
        ordinal_position=2,
        column_name="email",
        data_type="varchar(255)",
        is_nullable=True,
        column_default=None,
    )
    mock_client.call_tool.assert_awaited_once_with(
        "get_table_schema", {"schema": "public", "table_name": "customers"}
    )


@pytest.mark.asyncio
async def test_dry_run_query(client):
    mock_result = _server_text_result("Query is valid. No security issues detected.")

    with _mock_client_context(client, call_tool_return=mock_result) as mock_client:
        result = await client.dry_run_query("SELECT id FROM customers LIMIT 10")

    assert isinstance(result, DryRunResult)
    assert result.valid is True
    assert result.message == "Query is valid. No security issues detected."
    assert result.error is None
    mock_client.call_tool.assert_awaited_once_with(
        "dry_run_query", {"query": "SELECT id FROM customers LIMIT 10"}
    )


@pytest.mark.asyncio
async def test_execute_query_parses_structured_rows(client):
    mock_result = _server_text_result(
        "Results: 2 row(s) in 12.3ms\n\n"
        "id | full_name | balance\n"
        "------------------------\n"
        "1 | Alice | 100.5\n"
        "2 | Bob | NULL"
    )

    with _mock_client_context(client, call_tool_return=mock_result) as mock_client:
        rows = await client.execute_query("SELECT id, full_name, balance FROM customers LIMIT 2")

    assert rows == [
        {"id": 1, "full_name": "Alice", "balance": 100.5},
        {"id": 2, "full_name": "Bob", "balance": None},
    ]
    mock_client.call_tool.assert_awaited_once_with(
        "execute_query", {"query": "SELECT id, full_name, balance FROM customers LIMIT 2"}
    )
