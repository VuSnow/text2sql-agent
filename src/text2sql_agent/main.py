import logging

from fastapi import FastAPI

from text2sql_agent.config import settings
from text2sql_agent.mcp_client import create_mcp_client

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("text2sql_agent")

app = FastAPI(title="text2sql-agent", version="0.1.0")
mcp_client = create_mcp_client()


@app.on_event("startup")
async def startup() -> None:
    logger.info("Starting text2sql-agent (model=%s)", settings.llm_model)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    mcp_ok = await mcp_client.health_check()
    return {
        "status": "ok" if mcp_ok else "degraded",
        "mcp_server": settings.postgresql_mcp_server_url,
        "mcp_connected": mcp_ok,
    }
