# text2sql-agent

Text2SQL agent that converts natural language questions into PostgreSQL queries.
Built with LangGraph for agentic workflow, connects to `postgresql-mcp-server`
via MCP protocol for schema exploration and query validation, uses ChromaDB for
RAG-based SQL example retrieval.

- **LLM:** OpenAI GPT (generation) + AWS Bedrock Titan (embeddings)
- **Transport:** FastMCP Streamable HTTP
- **Vector Store:** ChromaDB with Bedrock embeddings + optional Cohere reranker

## Architecture

```
User Question (natural language)
     │
     ▼
┌─────────────────┐
│  FastAPI Server │  POST /query/preview, /query/execute, /query/stream
│  (port 8080)    │
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
│  retrieve_schema (MCP + NL enrichment from docs)           │
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
│ OpenAI API      │   │   ChromaDB   │  │ postgresql-mcp-server │
│ (GPT-4o-mini)   │   │  + Bedrock   │  │ (schema, dry_run,     │
│                 │   │  embeddings  │  │  execute, policy)     │
└─────────────────┘   └──────────────┘  └───────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.
See [docs/PLAN.md](docs/PLAN.md) for implementation plan.
See [docs/SETUP.md](docs/SETUP.md) for step-by-step setup & run guide.

## Features

- **Intent Classification** — rejects unsafe/unsupported queries before SQL generation
- **Clarification Flow** — asks targeted questions for ambiguous input instead of guessing
- **MCP Integration** — connects to `postgresql-mcp-server` for schema exploration and query validation/execution
- **Schema Enrichment** — merges raw MCP schema with business-level NL descriptions
- **Dual Provider** — OpenAI GPT for generation, AWS Bedrock Titan for embeddings
- **RAG Pipeline** — vector similarity search over curated SQL examples using ChromaDB + optional reranking
- **Self-Repair Loop** — validates SQL via `dry_run_query`, auto-fixes errors up to N retries
- **Semantic Validation** — LLM-based check for join correctness, aggregation logic, date filters
- **Preview by Default** — returns SQL without executing unless explicitly requested
- **Hard Security Boundary** — MCP server enforces AST validation, column policy, PII masking
- **FastAPI Server** — REST API with streaming support for real-time responses

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env: set LLM_API_KEY, AWS_PROFILE, POSTGRESQL_MCP_SERVER_URL

# Seed RAG data into ChromaDB
python -m text2sql_agent.rag.seed

# Run (requires postgresql-mcp-server on port 8000)
uvicorn text2sql_agent.main:app --host 0.0.0.0 --port 8080 --reload
```

For full setup including database and MCP server, see [docs/SETUP.md](docs/SETUP.md).

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRESQL_MCP_SERVER_URL` | MCP server endpoint | `http://localhost:8000/mcp` |
| `LLM_PROVIDER` | LLM provider (`openai` or `bedrock`) | `openai` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `LLM_API_KEY` | OpenAI API key | — |
| `EMBEDDING_PROVIDER` | Embedding provider (`bedrock` or `openai`) | `bedrock` |
| `EMBEDDING_MODEL_ID` | Embedding model | `amazon.titan-embed-text-v2:0` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |
| `AWS_PROFILE` | AWS credentials profile | `btc-bedrock` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./data/chroma` |
| `RERANKER_ENABLED` | Enable Cohere reranker | `false` |
| `MAX_REPAIR_ATTEMPTS` | SQL repair retry limit | `3` |
| `RAG_TOP_K` | Number of similar examples to retrieve | `10` |
| `TABLE_ALLOWLIST` | Comma-separated allowed tables (empty = all) | — |
| `DEFAULT_EXECUTE` | Execute queries by default | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Project Structure

```
src/text2sql_agent/
├── main.py                # FastAPI app entry point
├── config.py              # Pydantic Settings (env-based config)
├── models.py              # Request/response Pydantic models
├── policy.py              # Policy enforcement logic
├── agent/                 # LangGraph workflow
│   ├── graph.py           # Agent graph definition
│   ├── state.py           # Agent state schema
│   └── nodes/             # Individual workflow nodes
│       ├── classify.py        # Intent classification
│       ├── clarify.py         # Clarification question generation
│       ├── scope.py           # Schema scope selection
│       ├── schema.py          # Schema retrieval + enrichment
│       ├── rag.py             # SQL example retrieval
│       ├── generate.py        # SQL generation via LLM
│       ├── validate.py        # Validation via MCP dry_run
│       ├── semantic_check.py  # Semantic correctness check
│       ├── repair.py          # SQL repair via LLM
│       └── execute.py         # Conditional execution
├── mcp_client/            # MCP client connector (layered)
│   ├── base.py            # BaseMCPClient + BaseSQLMCPClient
│   ├── factory.py         # Registry-based client factory
│   ├── models.py          # MCP response models
│   └── postgresql_client.py  # PostgreSQL MCP client (Streamable HTTP)
├── rag/                   # Vector store & embedding
│   ├── embeddings.py      # Bedrock Titan embedding client
│   ├── reranker.py        # Bedrock Cohere reranker
│   ├── store.py           # ChromaDB operations (2 collections)
│   └── seed.py            # Seed schema + examples into vector store
└── llm/                   # LLM provider
    ├── provider.py        # Provider factory (OpenAI / Bedrock)
    └── prompts/           # Prompt templates
        ├── classification.py
        ├── clarification.py
        ├── generation.py
        ├── repair.py
        └── semantic_check.py

data/
├── docs/              # Table descriptions (markdown, for RAG seeding)
├── examples/          # Curated SQL examples (markdown, for RAG seeding)
├── csv/               # Sample CSV data
├── sql/               # SQL schema + seed data
├── chroma/            # ChromaDB persistence (gitignored)
├── prompts/           # Prompt templates (reference)
└── scripts/           # Utility scripts

tests/
├── unit/              # Unit tests
├── integration/       # RAG accuracy tests
├── manual/            # E2E smoke tests & advanced test suite
└── results/           # Test result JSON reports
```

## Manual Smoke Tests

Ensure `postgresql-mcp-server` is running on port 8000:

```bash
cd ../postgresql-mcp-server
fastmcp run src/postgresql_mcp/app.py:mcp --transport streamable-http --port 8000
```

Run MCP smoke test:

```bash
python tests/manual/test_mcp_smoke.py
```

Run agent health smoke test (requires agent running on port 8080):

```bash
python tests/manual/test_agent_health_smoke.py
```

Run advanced E2E test suite:

```bash
python tests/manual/test_agent_advanced.py
python tests/manual/test_agent_advanced.py --category multi_join
python tests/manual/test_agent_advanced.py --report
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

## Roadmap

**Current:** Single PostgreSQL backend via `postgresql-mcp-server`.

**Planned:**
- Multi-backend support (BigQuery, MySQL) via registry-based factory
- Evaluation framework with automated accuracy measurement
- Cross-database queries via federated query engine

See [docs/PLAN.md](docs/PLAN.md) for details.

## License

Apache 2.0
