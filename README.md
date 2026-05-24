# text2sql-agent

Text2SQL agent that converts natural language questions into PostgreSQL queries.
Built with LangGraph for agentic workflow, connects to `postgresql-mcp-server`
via MCP protocol for schema exploration and query validation, uses ChromaDB for
RAG-based SQL example retrieval, and supports multiple LLM providers.

## Architecture

```
User Question (natural language)
     │
     ▼
┌─────────────────┐
│  FastAPI Server │  POST /query, POST /query/stream
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│           LangGraph Agent Workflow           │
│                                              │
│  ┌─────────────┐    ┌────────────────────┐   │
│  │ 1. Schema   │───▶│ 2. RAG Examples    │   │
│  │   Retrieval │    │   Retrieval        │   │
│  └─────────────┘    └────────┬───────────┘   │
│        │                     │               │
│        │    MCP Protocol     │  ChromaDB     │
│        ▼                     ▼               │
│  ┌─────────────┐    ┌────────────────────┐   │
│  │ 3. SQL      │───▶│ 4. Validate &      │   │
│  │   Generation│    │   Repair (loop)    │   │
│  └─────────────┘    └────────────────────┘   │
│        │                     │               │
│        │  LLM API           │  MCP Protocol  │
│        ▼                     ▼               │
│  ┌──────────────────────────────────────┐    │
│  │         Final SQL + Results          │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
         │                     │
         ▼                     ▼
┌─────────────────┐   ┌───────────────────────┐
│ LLM Provider    │   │ postgresql-mcp-server │
│ (Gemini/GPT/    │   │ (schema, dry_run,     │
│  Claude)        │   │  execute_query)       │
└─────────────────┘   └───────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.
See [docs/PLAN.md](docs/PLAN.md) for implementation plan.

## Features

- **MCP Integration** — connects to `postgresql-mcp-server` for schema exploration and query validation/execution
- **Multi-LLM Support** — Google Gemini, OpenAI GPT-4, Anthropic Claude (configurable via env)
- **RAG Pipeline** — vector similarity search over curated SQL examples using ChromaDB
- **Self-Repair Loop** — validates SQL via `dry_run_query`, auto-fixes errors up to N retries
- **FastAPI Server** — REST API with streaming support for real-time responses
- **Stateful Agent** — LangGraph-based workflow with explicit state transitions

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your LLM API key and MCP server URL

# Ensure postgresql-mcp-server is running
# See: https://github.com/your-org/postgresql-mcp-server

# Seed SQL examples into ChromaDB
python -m text2sql_agent.rag.seed

# Run
uvicorn text2sql_agent.api.app:app --reload --port 8001

# Or with Docker
docker compose up
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_SERVER_URL` | postgresql-mcp-server endpoint | `http://localhost:8000` |
| `LLM_PROVIDER` | `gemini` / `openai` / `anthropic` | `gemini` |
| `LLM_MODEL` | Model name | `gemini-2.0-flash` |
| `LLM_API_KEY` | API key for chosen provider | — |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./data/chroma` |
| `MAX_REPAIR_ATTEMPTS` | SQL repair retry limit | `3` |
| `RAG_TOP_K` | Number of similar examples to retrieve | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Project Structure

```
src/text2sql_agent/
├── api/              # FastAPI endpoints
│   └── app.py
├── agent/            # LangGraph workflow
│   ├── graph.py      # Agent graph definition
│   ├── state.py      # Agent state schema
│   └── nodes/        # Individual workflow nodes
│       ├── schema.py     # Schema retrieval via MCP
│       ├── rag.py        # SQL example retrieval
│       ├── generate.py   # SQL generation via LLM
│       └── validate.py   # Validation & repair loop
├── mcp/              # MCP client connector
│   └── client.py
├── rag/              # Vector store & embedding
│   ├── store.py      # ChromaDB operations
│   └── seed.py       # Seed examples into vector store
├── llm/              # LLM provider abstraction
│   └── provider.py
└── config.py         # Settings & env config

data/
└── examples/         # Curated SQL examples (YAML/JSON)

tests/
├── unit/
└── integration/
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/query` | Convert NL question to SQL and execute |
| `POST` | `/query/stream` | Same as above with SSE streaming |
| `GET` | `/health` | Health check |

## License

Apache 2.0
