"""Smoke test direct MCP calls from text2sql-agent.

Usage:
    POSTGRESQL_MCP_SERVER_URL="http://127.0.0.1:8000/mcp/" \
    conda run -n eog-agent python tests/manual/test_mcp_smoke.py
"""

import asyncio
from pprint import pprint

from text2sql_agent.mcp_client import PostgreSQLMCPClient


async def main() -> None:
    client = PostgreSQLMCPClient()

    print("server_url:", client.server_url)

    print("\nhealth_check:")
    print(await client.health_check())

    print("\nlist_schemas:")
    pprint(await client.list_schemas())

    print("\nlist_tables(public):")
    pprint(await client.list_tables("public"))

    print("\nget_table_schema(public.customers):")
    pprint(await client.get_table_schema("public", "customers"))

    print("\ndry_run_query:")
    pprint(
        await client.dry_run_query(
            "SELECT id, full_name, status FROM public.customers LIMIT 5"
        )
    )

    print("\nexecute_query:")
    pprint(
        await client.execute_query(
            "SELECT id, full_name, status FROM public.customers LIMIT 5"
        )
    )


if __name__ == "__main__":
    asyncio.run(main())