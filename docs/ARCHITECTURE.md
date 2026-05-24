# Architecture

## System Overview

`text2sql-agent` is a production-safe stateful agent that translates natural
language questions into PostgreSQL SQL queries. It delegates all database
operations to `postgresql-mcp-server` via the Model Context Protocol (MCP),
ensuring security guardrails remain enforced at the data layer.

**Design principle:** Agent understands policy to generate SQL correctly from
the start. MCP server enforces policy as the hard boundary. Defense in depth,
not duplicated logic.

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          text2sql-agent                                   │
│                                                                           │
│  ┌───────────┐    ┌────────────────────────────────────────────────────┐  │
│  │  FastAPI  │──▶ │              LangGraph Agent                       │  │
│  │  (port    │    │                                                    │  │
│  │   8001)   │    │  START                                             │  │
│  └───────────┘    │    ↓                                               │  │
│                   │  classify_request ─── unsafe? ──▶ REJECT           │  │
│                   │    ↓                                               │  │
│                   │  select_schema_scope                               │  │
│                   │    ↓                                               │  │
│                   │  retrieve_schema (MCP, scoped)                     │  │
│                   │    ↓                                               │  │
│                   │  retrieve_examples (RAG, filtered by scope)        │  │
│                   │    ↓                                               │  │
│                   │  generate_sql (LLM, policy-aware prompt)           │  │
│                   │    ↓                                               │  │
│                   │  validate_sql (MCP: dry_run_query)                 │  │
│                   │    ↓                                               │  │
│                   │  repair_or_abort ─── policy_violation? ──▶ ABORT   │  │
│                   │    ↓                                               │  │
│                   │  preview / execute                                 │  │
│                   │    ↓                                               │  │
│                   │  END                                               │  │
│                   └────────────────────────────────────────────────────┘  │
│                   │                  │              │                     │
│                 MCP Client      ChromaDB       LLM Client                 │
└───────────────────┼──────────────────┼──────────────┼─────────────────────┘
                    │                  │              │
                    ▼                  ▼              ▼
         ┌──────────────────┐  ┌────────────┐  ┌───────────────┐
         │ postgresql-mcp-  │  │  ChromaDB  │  │  LLM API      │
         │ server (port     │  │  (embedded/│  │  (Gemini/     │
         │ 8000)            │  │   persist) │  │   OpenAI/     │
         │                  │  └────────────┘  │   Anthropic)  │
         │ ENFORCES:        │                  └───────────────┘
         │ - AST validation │
         │ - column policy  │
         │ - row limit      │
         │ - PII masking    │
         └──────────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │   PostgreSQL     │
         └──────────────────┘
```

## Security Boundary Model

```
┌──────────────────────────────────────────────────────────────────┐
│  AGENT RESPONSIBILITY (understand policy, generate correctly)    │
│                                                                  │
│  - Classify intent (reject unsafe/unsupported)                   │
│  - Scope schema (only fetch allowed tables)                      │
│  - Policy-aware prompts (SELECT only, LIMIT, no SELECT *)        │
│  - Error classification (abort on policy violation)              │
│  - Preview by default (no auto-execute)                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼ MCP calls
┌──────────────────────────────────────────────────────────────────┐
│  MCP SERVER RESPONSIBILITY (enforce policy, hard boundary)       │
│                                                                  │
│  - AST-based SQL validation (sqlglot)                            │
│  - Column-level access policy (allowlist per table)              │
│  - Critical pattern blocking (injection, advisory locks, etc.)   │
│  - Required filters enforcement                                  │
│  - Result row budget                                             │
│  - PII masking on output                                         │
│  - Audit logging                                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. FastAPI Server (`api/app.py`)

Entry point for external clients. Exposes REST endpoints:

- `POST /query/preview` — generate + validate SQL, return SQL only (default mode)
- `POST /query/execute` — generate + validate + execute, return SQL + results
- `POST /query/stream` — SSE streaming of agent step-by-step progress
- `GET /health` — readiness check

Request model:
```python
class QueryRequest(BaseModel):
    question: str
    execute: bool = False  # Alternative to separate endpoints
```

Responsibilities:
- Request validation (Pydantic models)
- Invoke LangGraph agent
- Respect execute flag (default: preview only)
- Format response / stream events
- Error handling & logging

### 2. LangGraph Agent (`agent/`)

Stateful workflow orchestrating the text-to-SQL pipeline with safety gates.

#### State Schema (`agent/state.py`)

```python
class Classification(TypedDict):
    request_type: str       # data_query | explanation | unsafe | unsupported | ambiguous
    requires_sql: bool
    risk_level: str         # low | medium | high
    reason: str
    safe_to_continue: bool

class ValidationResult(TypedDict):
    valid: bool
    error_type: str | None  # syntax | missing_column | policy_violation | timeout_risk | unknown
    message: str
    repairable: bool

class AgentState(TypedDict):
    # Input
    question: str
    execute: bool

    # Classification gate
    classification: Classification

    # Schema scope
    allowed_tables: list[str]       # From config allowlist
    candidate_tables: list[str]     # Selected for this query
    policy_context: str             # Policy rules injected into prompts

    # Retrieved context
    schema_context: str
    sql_examples: list[str]

    # Generation & validation
    generated_sql: str
    validation_result: ValidationResult | None
    repair_attempts: int

    # Output
    final_sql: str
    query_result: str | None
    error: str | None
```

#### Graph Definition (`agent/graph.py`)

```
START
  │
  ▼
classify_request
  │
  ├── safe_to_continue=false ──▶ END (rejection reason)
  │
  ▼
select_schema_scope
  │
  ▼
retrieve_schema
  │
  ▼
retrieve_examples
  │
  ▼
generate_sql
  │
  ▼
validate_sql
  │
  ├── valid=true ──▶ maybe_execute ──▶ END (success)
  │
  ├── repairable=true AND attempts < max ──▶ repair_sql ──▶ validate_sql
  │
  └── repairable=false OR attempts >= max ──▶ END (error)
```

#### Nodes (`agent/nodes/`)

| Node | Purpose | External Call | Abort Condition |
|------|---------|---------------|-----------------|
| `classify_request` | Determine if question is safe/supported | LLM API | unsafe, unsupported, ambiguous |
| `select_schema_scope` | Pick candidate tables via semantic search | ChromaDB: `schema_descriptions` collection | No candidate tables found |
| `retrieve_schema` | Fetch exact schema for candidate tables | MCP: `get_table_schema`, `get_constraints` | — |
| `retrieve_examples` | Find similar SQL examples (scoped) | ChromaDB: `sql_examples` collection (filtered) | — |
| `generate_sql` | Generate SQL with policy-aware prompt | LLM API | — |
| `validate_sql` | Validate via MCP, classify error type | MCP: `dry_run_query` | — |
| `repair_sql` | Fix SQL based on error (if repairable) | LLM API | policy_violation → abort |
| `maybe_execute` | Execute if `execute=true` | MCP: `execute_query` | execute=false → skip |

### 3. MCP Client (`mcp/client.py`)

HTTP client that communicates with `postgresql-mcp-server` using the MCP protocol
(JSON-RPC over HTTP/SSE).

Available MCP tools on the server:

| Tool | Purpose | Used by |
|------|---------|---------|
| `list_schemas` | List all schemas | `retrieve_schema` |
| `list_tables` | List tables in schema | `select_schema_scope`, `retrieve_schema` |
| `get_table_schema` | Column definitions | `retrieve_schema` |
| `get_indexes` | Index info | `retrieve_schema` (optional) |
| `get_constraints` | FK/PK/UNIQUE | `retrieve_schema` |
| `get_column_values` | Sample values | `retrieve_schema` (optional) |
| `dry_run_query` | Validate SQL without executing | `validate_sql` |
| `execute_query` | Execute validated SQL | `maybe_execute` |
| `explain_query` | Execution plan | Future optimization |

Client implementation:
- Uses `httpx.AsyncClient` for HTTP transport
- Supports MCP SSE transport (stdio not needed since server is remote)
- Connection pooling and retry with backoff
- Timeout configuration

### 4. ChromaDB Vector Store (`rag/`)

One ChromaDB instance with **two collections** serving different purposes:

```
┌─────────────────────────────────────────────────────────────┐
│  ChromaDB (1 instance, persistent volume)                   │
│                                                             │
│  ┌───────────────────────────┐  ┌─────────────────────────┐ │
│  │ Collection:               │  │ Collection:             │ │
│  │ schema_descriptions       │  │ sql_examples            │ │
│  │                           │  │                         │ │
│  │ • 1 doc per table         │  │ • 1 doc per example     │ │
│  │ • embed: table + column   │  │ • embed: NL question    │ │
│  │   business descriptions   │  │ • metadata: SQL query   │ │
│  │ • for: table selection    │  │ • for: SQL generation   │ │
│  │ • used by:                │  │ • used by:              │ │
│  │   select_schema_scope     │  │   retrieve_examples     │ │
│  └───────────────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### Collection 1: `schema_descriptions` (table selection)

Stores **business-level descriptions** of tables and columns. Used to semantically
match user questions to relevant tables.

**Document format** (one per table, concatenated):
```
Bảng customers - Bảng lưu thông tin khách hàng cá nhân của ngân hàng.
Các cột: id (mã khách hàng, primary key), full_name (họ và tên đầy đủ),
email (email liên hệ, dùng cho đăng nhập), phone (số điện thoại chính),
balance (số dư tài khoản hiện tại VND), status (trạng thái: active/suspended/closed),
created_at (ngày mở tài khoản)
```

**Metadata:**
```
  table_name: "customers"
  schema: "public"
  columns: "id,full_name,email,phone,balance,status,created_at"
```

**Source file:** `data/schema/tables.yaml`
```yaml
tables:
  - name: customers
    schema: public
    description: "Bảng lưu thông tin khách hàng cá nhân của ngân hàng"
    columns:
      - name: id
        type: bigint
        description: "Mã khách hàng (primary key, auto-increment)"
      - name: full_name
        type: varchar(255)
        description: "Họ và tên đầy đủ của khách hàng"
      - name: balance
        type: numeric(15,2)
        description: "Số dư tài khoản hiện tại (đơn vị: VND)"
      # ...
```

**Why not just use MCP `get_table_schema`?**

| | `schema_descriptions` (ChromaDB) | `get_table_schema` (MCP) |
|---|---|---|
| **Contains** | Business meaning, NL descriptions | Technical: column name, type, nullable, default |
| **Used when** | Finding which tables are relevant to a question | Getting exact schema to generate SQL |
| **Search type** | Semantic (vector similarity) | Exact lookup (need table name already) |

Both are needed: ChromaDB to **find** tables, MCP to **get** precise schema.

#### Collection 2: `sql_examples` (RAG for generation)

Stores curated NL→SQL pairs for few-shot prompting.

**Embedding strategy:**
- Embed the natural language question (not the SQL) as the document
- Store the corresponding SQL as metadata
- At query time: embed user question → find similar questions → return their SQL

**Collection schema:**
```
  - document: Natural language question
  - metadata:
      - sql: The actual SQL query
      - tables: Comma-separated table names used
      - complexity: simple | medium | complex
      - tags: Optional category tags
```

**Scoped retrieval:** At query time, filter by `tables` metadata to only return
examples that use tables within the current `candidate_tables` scope.

**Source file:** `data/examples/*.yaml`
```yaml
examples:
  - question: "Tổng số tiền giao dịch theo khách hàng tháng trước"
    sql: |
      SELECT c.full_name, SUM(t.amount) as total
      FROM customers c
      JOIN transactions t ON c.id = t.customer_id
      WHERE t.created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
        AND t.created_at < DATE_TRUNC('month', CURRENT_DATE)
      GROUP BY c.full_name
      ORDER BY total DESC
      LIMIT 100
    tables: ["customers", "transactions"]
    complexity: medium
```

**Curation rules (operational, not code):**
- Examples must be reviewed before merge
- No real sample values / PII
- No tenant-specific SQL in multi-tenant setups
- Always use explicit column names (no `SELECT *`)
- Always include LIMIT
- `tables` metadata must match currently allowed schema

#### Seed Pipeline (`rag/seed.py`)

Single script that populates both collections at startup:

```
python -m text2sql_agent.rag.seed

  ┌─────────────────────────────────┐
  │  Load data/schema/tables.yaml   │
  │  → concat table + column descs  │
  │  → embed                        │
  │  → upsert: schema_descriptions  │
  └─────────────────────────────────┘
              +
  ┌─────────────────────────────────┐
  │  Load data/examples/*.yaml      │
  │  → embed NL questions           │
  │  → upsert: sql_examples         │
  └─────────────────────────────────┘
```

- Idempotent (deterministic IDs based on table name / question hash)
- Runs at container startup or manually
- When tables change → update `data/schema/tables.yaml` → re-seed

### 5. LLM Provider (`llm/provider.py`)

Abstraction over multiple LLM providers using LangChain's chat model interface.

```python
def get_llm(provider: str, model: str, api_key: str, temperature: float) -> BaseChatModel:
    match provider:
        case "gemini":    return ChatGoogleGenerativeAI(...)
        case "openai":    return ChatOpenAI(...)
        case "anthropic": return ChatAnthropic(...)
```

Used in three nodes:
- `classify_request`: Structured output for intent classification
- `generate_sql`: System prompt with schema + examples + policy → generate SQL
- `repair_sql`: System prompt with error + original SQL → fix SQL

#### Policy-Aware SQL Generation Prompt

The `generate_sql` prompt includes policy context:

```
You are a PostgreSQL SQL expert. Generate a SQL query for the user's question.

RULES (strictly enforced):
- Only SELECT statements
- Never use SELECT * — always specify columns
- Always include LIMIT (max 100 unless user specifies)
- Only use these tables: {candidate_tables}
- Only use these columns: {allowed_columns}
- Do not access: {denied_columns}
- No subqueries deeper than 2 levels
- No more than 3 JOINs

SCHEMA:
{schema_context}

EXAMPLES:
{sql_examples}

USER QUESTION: {question}
```

### 6. Configuration (`config.py`)

Pydantic Settings loading from `.env`:

```python
class Settings(BaseSettings):
    # MCP Server
    mcp_server_url: str = "http://localhost:8000"

    # LLM
    llm_provider: LLMProvider  # gemini | openai | anthropic
    llm_model: str = "gemini-2.0-flash"
    llm_api_key: str = ""
    llm_temperature: float = 0.0

    # RAG / ChromaDB
    chroma_persist_dir: Path = Path("./data/chroma")
    rag_top_k: int = 5

    # Agent behavior
    max_repair_attempts: int = 3
    default_execute: bool = False  # Preview by default

    # Schema scope
    table_allowlist: list[str] = []  # Empty = all tables from MCP
    schema_name: str = "public"

    # Logging
    log_level: str = "INFO"
```

## Data Flow (Happy Path — Preview Mode)

1. User sends: `POST /query/preview {"question": "Show me top 10 customers by balance"}`
2. FastAPI invokes LangGraph agent with `execute=false`
3. **classify_request**: LLM → `{request_type: "data_query", safe_to_continue: true}`
4. **select_schema_scope**: ChromaDB `schema_descriptions` → semantic match → `candidate_tables: ["customers"]`
5. **retrieve_schema**: MCP → `get_table_schema("customers")` → exact column definitions
6. **retrieve_examples**: ChromaDB query (filtered: tables contains "customers") → 5 examples
7. **generate_sql**: LLM with policy prompt → `SELECT name, balance FROM customers ORDER BY balance DESC LIMIT 10`
8. **validate_sql**: MCP → `dry_run_query(sql)` → `{valid: true}`
9. **maybe_execute**: `execute=false` → skip
10. Return: `{sql: "SELECT ...", executed: false}`

## Data Flow (Repair Path)

1. Steps 1–7 same as above
2. **validate_sql**: MCP → `dry_run_query(sql)` → `{valid: false, error_type: "missing_column", repairable: true}`
3. **repair_sql**: LLM with error context → produces fixed SQL
4. Loop back to **validate_sql** (up to `max_repair_attempts`)
5. If still failing → return error to user

## Data Flow (Rejection Path)

1. User sends: `POST /query/preview {"question": "Delete all customer records"}`
2. **classify_request**: LLM → `{request_type: "unsafe", safe_to_continue: false, reason: "destructive intent"}`
3. Agent returns immediately: `{error: "Request rejected: destructive intent detected"}`

## Data Flow (Policy Violation — No Repair)

1. User sends: `POST /query/execute {"question": "Show me all employee salaries"}`
2. **classify_request**: passes (it's a data query)
3. **select_schema_scope**: `employees` not in `table_allowlist` → abort
4. Return: `{error: "Table 'employees' is not accessible"}`

Alternative: if table is allowed but column isn't:
5. **generate_sql** produces SQL accessing denied column
6. **validate_sql**: MCP → `{valid: false, error_type: "policy_violation", repairable: false}`
7. Agent aborts immediately (no repair loop)

## Security Considerations

- **No direct DB access** — all queries go through `postgresql-mcp-server` guardrails
- **Intent classification** — reject unsafe/unsupported requests before SQL generation
- **Scoped schema** — agent only sees tables/columns it's allowed to access
- **Policy-aware generation** — LLM prompted to follow rules, reducing policy violations
- **Error classification** — policy violations cause abort, not repair attempts
- **Preview by default** — no execution unless explicitly requested
- **Input sanitization** — user questions are treated as text, never interpolated into SQL
- **API key management** — LLM keys in env vars, never logged
- **Rate limiting** — delegated to MCP server; optionally add FastAPI rate limiter
- **No PII exposure** — MCP server handles PII masking on results

## Deployment

```
┌─────────────────────────────────────────┐
│           Docker Compose                │
│                                         │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ text2sql-    │  │ postgresql-mcp- │  │
│  │ agent:8001   │─▶│ server:8000     │  │
│  └──────────────┘  └────────┬────────┘  │
│         │                   │           │
│  ┌──────┴───────┐  ┌────────▼────────┐  │
│  │  ChromaDB    │  │   PostgreSQL    │  │
│  │  (volume)    │  │   (external)    │  │
│  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────┘
```

- `text2sql-agent` and `postgresql-mcp-server` run as separate containers
- ChromaDB uses a persistent Docker volume
- PostgreSQL is external (managed DB or separate container)
- LLM APIs are called over the internet (no local model)
