import logging

from fastapi import FastAPI

from text2sql_agent.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("text2sql_agent")

app = FastAPI(title="text2sql-agent", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    logger.info("Starting text2sql-agent (model=%s)", settings.llm_model)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mcp_server": settings.mcp_server_url}
