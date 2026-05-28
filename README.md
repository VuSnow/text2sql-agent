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
│  FastAPI Server │  POST /query/preview, /query/execute, /query/stream
└────────┬────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│              LangGraph Agent Workflow                       │
│                                                            │
│  classify_request                                          │
│    ├── unsafe/unsupported ──▶ REJECT                       │
│    ├── ambiguous ──▶ clarify_question ──▶ NEEDS_CLARIFY    │
│    ▼                                                       │
│  select_schema_scope (ChromaDB: schema_descriptions)       │
│    ▼                                                       │
│  retrieve_schema (MCP + NL enrichment from YAML)           │
│    ▼                                                       │
│  retrieve_examples (ChromaDB: sql_examples, scoped)        │
│    ▼                                                       │
│  generate_sql (LLM, policy-aware prompt)                   │
│    ▼                                                       │
│  validate_sql (MCP: dry_run_query)                         │
│    ├── repairable error ──▶ repair_sql ──▶ loop            │
│    ▼                                                       │
│  semantic_check_sql (LLM: join/aggregation/logic check)    │
│    ├── severity=error ──▶ repair_sql ──▶ loop              │
│    ▼                                                       │
│  maybe_execute ──▶ END (success)                           │
└────────────────────────────────────────────────────────────┘
         │                     │                │
         ▼                     ▼                ▼
┌─────────────────┐   ┌──────────────┐  ┌───────────────────────┐
│ LLM Provider    │   │   ChromaDB   │  │ postgresql-mcp-server │
│ (Gemini/GPT/    │   │  (embedded)  │  │ (schema, dry_run,     │
│  Claude)        │   │              │  │  execute, policy)     │
└─────────────────┘   └──────────────┘  └───────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.
See [docs/PLAN.md](docs/PLAN.md) for implementation plan.

## Features

- **Intent Classification** — rejects unsafe/unsupported queries before SQL generation
- **Clarification Flow** — asks targeted questions for ambiguous input instead of guessing
- **MCP Integration** — connects to `postgresql-mcp-server` for schema exploration and query validation/execution
- **Schema Enrichment** — merges raw MCP schema with business-level NL descriptions
- **Multi-LLM Support** — Google Gemini, OpenAI GPT-4, Anthropic Claude (configurable via env)
- **RAG Pipeline** — vector similarity search over curated SQL examples using ChromaDB
- **Self-Repair Loop** — validates SQL via `dry_run_query`, auto-fixes errors up to N retries
- **Semantic Validation** — LLM-based check for join correctness, aggregation logic, date filters
- **Preview by Default** — returns SQL without executing unless explicitly requested
- **Hard Security Boundary** — MCP server enforces AST validation, column policy, PII masking
- **Evaluation Framework** — automated accuracy measurement and regression detection
- **FastAPI Server** — REST API with streaming support for real-time responses

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
| `TABLE_ALLOWLIST` | Comma-separated allowed tables (empty = all) | — |
| `DEFAULT_EXECUTE` | Execute queries by default | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Project Structure

```
src/text2sql_agent/
├── api/              # FastAPI endpoints
│   ├── app.py
│   └── models.py     # Request/response Pydantic models
├── agent/            # LangGraph workflow
│   ├── graph.py      # Agent graph definition
│   ├── state.py      # Agent state schema
│   └── nodes/        # Individual workflow nodes
│       ├── classify.py       # Intent classification
│       ├── clarify.py        # Clarification question generation
│       ├── scope.py          # Schema scope selection
│       ├── schema.py         # Schema retrieval + enrichment
│       ├── rag.py            # SQL example retrieval
│       ├── generate.py       # SQL generation via LLM
│       ├── validate.py       # Validation via MCP dry_run
│       ├── semantic_check.py # Semantic correctness check
│       ├── repair.py         # SQL repair via LLM
│       └── execute.py        # Conditional execution
├── mcp/              # MCP client connector
│   └── client.py
├── rag/              # Vector store & embedding
│   ├── store.py      # ChromaDB operations (2 collections)
│   └── seed.py       # Seed schema + examples into vector store
├── llm/              # LLM provider abstraction
│   ├── provider.py
│   └── prompts.py    # All prompt templates
├── eval/             # Evaluation framework
│   ├── runner.py     # Eval runner
│   ├── sql_compare.py # SQL equivalence checker
│   └── metrics.py    # Metrics computation
└── config.py         # Settings & env config

data/
├── schema/           # Table descriptions (YAML)
│   └── tables.yaml
├── examples/         # Curated SQL examples (YAML)
│   └── banking.yaml
└── eval/             # Evaluation dataset
    └── banking_eval.yaml

tests/
├── unit/
└── integration/
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/query/preview` | Generate + validate SQL, return SQL only (default) |
| `POST` | `/query/execute` | Generate + validate + execute, return SQL + results |
| `POST` | `/query/stream` | SSE streaming of agent step-by-step progress |
| `GET` | `/health` | Health check |

**Response types:**

```jsonc
// Success
{"status": "success", "sql": "SELECT ...", "executed": false, "warnings": [...]}

// Needs clarification
{"status": "needs_clarification", "original_question": "...", "questions": ["...", "..."]}

// Error
{"status": "error", "error": "...", "error_type": "rejected|policy_violation|..."}
```

## Evaluation

```bash
# Run evaluation suite
python -m text2sql_agent.eval.run --dataset data/eval/banking_eval.yaml

# Output: metrics report with per-case pass/fail + aggregate accuracy
```

Key metrics: Execution Accuracy (≥85%), Schema Linking (≥95%), Classification (≥98%), Policy Violation Rate (≤2%).

## License

Apache 2.0
