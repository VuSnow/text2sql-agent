# Implementation Plan

## Overview

Phase-by-phase implementation of `text2sql-agent` — a **production-safe**
PostgreSQL Text2SQL agent using LangGraph, MCP protocol, ChromaDB RAG, and
multi-provider LLM support.

**Target stack:** Python 3.11+, FastAPI, LangGraph, ChromaDB, httpx

**Design stance:** Production-safe skeleton from Phase 1. Safety gates
(classification, scope, policy-aware generation, error classification) are
built into the foundation, not bolted on later. Implementation stays minimal
— no over-engineering.

---

## Phase 1: Project Foundation

**Goal:** Runnable project skeleton with configuration, policy config, and health endpoint.

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create `pyproject.toml` with all dependencies | `pyproject.toml` |
| 1.2 | Create `.env.example` with all config vars | `.env.example` |
| 1.3 | Create `.gitignore` | `.gitignore` |
| 1.4 | Implement `config.py` with Pydantic Settings (incl. `table_allowlist`, `default_execute=false`) | `src/text2sql_agent/config.py` |
| 1.5 | Create FastAPI app with `/health` endpoint | `src/text2sql_agent/api/app.py` |
| 1.6 | Verify: `uvicorn text2sql_agent.api.app:app` starts | — |

**Dependencies:** None
**Exit criteria:** Server starts, `/health` returns 200. Config loads with policy fields.

---

## Phase 2: MCP Client

**Goal:** Async client that can call `postgresql-mcp-server` tools.

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Implement MCP client with httpx (SSE transport) | `src/text2sql_agent/mcp/client.py` |
| 2.2 | Wrapper methods: `list_schemas`, `list_tables`, `get_table_schema`, `get_constraints`, `dry_run_query`, `execute_query` | same |
| 2.3 | Connection health check and retry logic | same |
| 2.4 | Unit tests with mocked responses | `tests/unit/test_mcp_client.py` |

**Dependencies:** Phase 1, running `postgresql-mcp-server`
**Exit criteria:** Can call MCP tools and get schema info from a test database.

---

## Phase 3: LLM Provider Abstraction

**Goal:** Configurable LLM client supporting Gemini, OpenAI, Claude + prompt templates.

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Implement provider factory using LangChain chat models | `src/text2sql_agent/llm/provider.py` |
| 3.2 | Prompt templates: classification, SQL generation (policy-aware), repair | `src/text2sql_agent/llm/prompts.py` |
| 3.3 | Unit tests for provider instantiation | `tests/unit/test_llm_provider.py` |

**Prompts to implement:**

**A. Classification prompt:**
```
Classify this user request. Output structured JSON.
- request_type: data_query | explanation | unsafe | unsupported | ambiguous
- requires_sql: bool
- risk_level: low | medium | high
- reason: brief explanation
- safe_to_continue: bool

UNSAFE examples: DELETE, DROP, INSERT, UPDATE, anything destructive
UNSUPPORTED examples: questions about non-data topics, requests for code generation
AMBIGUOUS examples: too vague to determine intent
```

**B. SQL generation prompt (policy-aware):**
```
RULES (strictly enforced):
- Only SELECT statements
- Never use SELECT * — always specify columns
- Always include LIMIT (max 100 unless user specifies)
- Only use these tables: {candidate_tables}
- Only use columns from the schema below
- No subqueries deeper than 2 levels
- No more than 3 JOINs
```

**C. Repair prompt:**
```
The SQL failed validation. Fix it following the same rules.
Original SQL: {sql}
Error: {error_message}
Error type: {error_type}
Do NOT attempt to access different tables or columns to work around policy.
```

**Dependencies:** Phase 1
**Exit criteria:** Can instantiate any provider and get structured responses.

---

## Phase 4: RAG — Vector Store & Seeding

**Goal:** ChromaDB with 2 collections: `schema_descriptions` (table selection) and `sql_examples` (SQL RAG). Both seeded from YAML.

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | ChromaDB store wrapper with 2 collections (schema + examples) | `src/text2sql_agent/rag/store.py` |
| 4.2 | Schema YAML format: table name, description, columns with types + NL descriptions | `data/schema/tables.yaml` |
| 4.3 | Create schema descriptions for banking domain tables | `data/schema/tables.yaml` |
| 4.4 | Example YAML format definition | `data/examples/README.md` |
| 4.5 | Create 20–30 seed SQL examples (various complexity) | `data/examples/banking.yaml` |
| 4.6 | Seed script: loads both YAML sources → embeds → upserts into both collections | `src/text2sql_agent/rag/seed.py` |
| 4.7 | Unit tests: schema search by NL question returns correct tables | `tests/unit/test_rag_store.py` |
| 4.8 | Unit tests: example search with table filter returns scoped results | same |

**Collection 1: `schema_descriptions`** (for `select_schema_scope` node):

```yaml
# data/schema/tables.yaml
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
      - name: status
        type: varchar(20)
        description: "Trạng thái: active, suspended, closed"
      - name: created_at
        type: timestamp
        description: "Ngày mở tài khoản"

  - name: transactions
    schema: public
    description: "Lịch sử tất cả giao dịch tài chính: chuyển khoản, rút tiền, nạp tiền"
    columns:
      - name: id
        type: bigint
        description: "Mã giao dịch (primary key)"
      - name: customer_id
        type: bigint
        description: "Mã khách hàng thực hiện giao dịch (FK → customers.id)"
      - name: type
        type: varchar(20)
        description: "Loại giao dịch: transfer, withdrawal, deposit"
      - name: amount
        type: numeric(15,2)
        description: "Số tiền giao dịch (VND), luôn dương"
      - name: created_at
        type: timestamp
        description: "Thời điểm giao dịch được thực hiện"
```

**Embed logic:** Concatenate table description + all column descriptions into 1 document per table.

**Collection 2: `sql_examples`** (for `retrieve_examples` node):

```yaml
# data/examples/banking.yaml
examples:
  - question: "Show me all customers with balance over 10000"
    sql: "SELECT full_name, balance FROM customers WHERE balance > 10000 LIMIT 100"
    tables: ["customers"]
    complexity: simple

  - question: "What is the total transaction amount per customer last month?"
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

**Scoped retrieval:** `query_examples()` accepts `table_filter: list[str]` to only return
examples whose `tables` metadata overlaps with candidate tables.

**Curation rules (documented in `data/examples/README.md`):**
- All examples must be reviewed before merge
- No real sample values or PII
- No tenant-specific SQL
- Always use explicit column names (no `SELECT *`)
- Always include LIMIT
- `tables` metadata must list all tables used

**Seed script behavior:**
```
python -m text2sql_agent.rag.seed

1. Load data/schema/tables.yaml
   → For each table: concat description + columns into document
   → Embed + upsert into "schema_descriptions" (ID = table_name)

2. Load data/examples/*.yaml
   → For each example: embed question
   → Upsert into "sql_examples" (ID = hash of question)

Idempotent. Safe to re-run.
```

**Dependencies:** Phase 1
**Exit criteria:** Seed both collections. Query `schema_descriptions` with NL question → get relevant table names. Query `sql_examples` with table filter → get scoped SQL.

---

## Phase 5: LangGraph Agent — Core Nodes

**Goal:** All nodes implemented with safety gates, testable in isolation.

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Define `AgentState` TypedDict (full state incl. classification, scope, policy) | `src/text2sql_agent/agent/state.py` |
| 5.2 | `classify_request` node — LLM structured output for intent classification | `src/text2sql_agent/agent/nodes/classify.py` |
| 5.3 | `select_schema_scope` node — semantic search in `schema_descriptions` + allowlist filter → candidate tables | `src/text2sql_agent/agent/nodes/scope.py` |
| 5.4 | `retrieve_schema` node — calls MCP for candidate tables only | `src/text2sql_agent/agent/nodes/schema.py` |
| 5.5 | `retrieve_examples` node — queries ChromaDB filtered by candidate tables | `src/text2sql_agent/agent/nodes/rag.py` |
| 5.6 | `generate_sql` node — policy-aware LLM prompt | `src/text2sql_agent/agent/nodes/generate.py` |
| 5.7 | `validate_sql` node — MCP `dry_run_query` + error classification | `src/text2sql_agent/agent/nodes/validate.py` |
| 5.8 | `repair_sql` node — LLM repair (abort if policy_violation) | `src/text2sql_agent/agent/nodes/repair.py` |
| 5.9 | `maybe_execute` node — execute only if `execute=true` | `src/text2sql_agent/agent/nodes/execute.py` |
| 5.10 | Unit tests for each node | `tests/unit/test_nodes.py` |

**Node detail — `classify_request`:**
```python
# Input: state.question
# Output: state.classification
# Abort if: safe_to_continue == false
# Implementation: LLM with structured output (JSON mode)
```

**Node detail — `select_schema_scope`:**
```python
# Input: state.question, config.table_allowlist
# Output: state.candidate_tables
# Logic:
#   1. Semantic search in ChromaDB "schema_descriptions" collection
#      → returns top-N tables matching the question
#   2. If table_allowlist is set → intersect results with allowlist
#   3. If no match found → fallback to full allowlist
# Abort if: no candidate tables identified after filtering
```

**Node detail — `validate_sql` (error classification):**
```python
# Input: state.generated_sql
# Output: state.validation_result
# Classification logic:
#   - MCP returns error containing "permission denied" / "access" → policy_violation
#   - MCP returns error containing "does not exist" → missing_column (repairable)
#   - MCP returns error containing "syntax error" → syntax (repairable)
#   - MCP returns success → valid
#   - Other → unknown (repairable with caution)
```

**Dependencies:** Phases 2, 3, 4
**Exit criteria:** Each node can be called independently with mock state. Classification rejects unsafe input. Validation classifies errors correctly.

---

## Phase 6: LangGraph Agent — Graph Assembly

**Goal:** Complete agent workflow with conditional routing and safety gates.

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | Assemble graph: nodes + edges + conditional routing | `src/text2sql_agent/agent/graph.py` |
| 6.2 | Conditional edge: classify → REJECT (if unsafe) or continue | same |
| 6.3 | Conditional edge: scope → ABORT (if no candidates) or continue | same |
| 6.4 | Conditional edge: validate → END (if valid) or repair/abort | same |
| 6.5 | Conditional edge: repair → validate (if repairable & attempts < max) or ABORT | same |
| 6.6 | Integration test: happy path | `tests/integration/test_agent.py` |
| 6.7 | Integration test: rejection path | same |
| 6.8 | Integration test: policy violation path | same |

**Graph routing logic:**
```python
def route_after_classify(state):
    if not state["classification"]["safe_to_continue"]:
        return "reject"
    return "select_schema_scope"

def route_after_validate(state):
    result = state["validation_result"]
    if result["valid"]:
        return "maybe_execute"
    if not result["repairable"]:
        return "abort"
    if state["repair_attempts"] >= settings.max_repair_attempts:
        return "abort"
    return "repair_sql"
```

**Dependencies:** Phase 5
**Exit criteria:** Agent handles all 4 flows: happy path, repair, rejection, policy violation abort.

---

## Phase 7: FastAPI Endpoints

**Goal:** REST API with preview/execute separation.

| Task | Description | Files |
|------|-------------|-------|
| 7.1 | Request/response Pydantic models | `src/text2sql_agent/api/models.py` |
| 7.2 | `POST /query/preview` — generate + validate SQL only | `src/text2sql_agent/api/app.py` |
| 7.3 | `POST /query/execute` — generate + validate + execute | same |
| 7.4 | `POST /query/stream` — SSE streaming of agent steps | same |
| 7.5 | Error handling middleware | same |
| 7.6 | Integration tests for API | `tests/integration/test_api.py` |

**Response model:**
```python
class QueryResponse(BaseModel):
    sql: str | None
    executed: bool
    result: list[dict] | None  # Only if executed
    classification: Classification
    error: str | None
    steps: list[str]  # Trace of nodes executed
```

**Default behavior:** `execute=false` unless explicitly set or using `/query/execute`.

**Dependencies:** Phase 6
**Exit criteria:** Can curl both preview and execute endpoints. Rejection returns proper error.

---

## Phase 8: Docker & Deployment

**Goal:** Containerized deployment with docker-compose.

| Task | Description | Files |
|------|-------------|-------|
| 8.1 | Dockerfile (multi-stage build) | `Dockerfile` |
| 8.2 | docker-compose.yml (agent + mcp-server) | `docker-compose.yml` |
| 8.3 | Startup script: seed ChromaDB on first run | `scripts/entrypoint.sh` |
| 8.4 | Health check integration | `docker-compose.yml` |

**Dependencies:** Phase 7
**Exit criteria:** `docker compose up` brings up full stack.

---

## Phase 9: Testing & Quality

**Goal:** Comprehensive test coverage and CI readiness.

| Task | Description | Files |
|------|-------------|-------|
| 9.1 | Unit test suite (≥80% coverage on core logic) | `tests/unit/` |
| 9.2 | Integration test suite (with test PostgreSQL) | `tests/integration/` |
| 9.3 | Safety-specific tests: injection attempts, policy bypass attempts | `tests/unit/test_safety.py` |
| 9.4 | Ruff linting + formatting config | `pyproject.toml` |
| 9.5 | mypy strict type checking | `pyproject.toml` |
| 9.6 | GitHub Actions CI (lint + test) | `.github/workflows/ci.yml` |

**Safety test cases (Phase 9.3):**
- User asks "DROP TABLE customers" → rejected at classification
- User asks "Show me all data" (ambiguous) → rejected or clarification
- Generated SQL accesses denied table → policy_violation, no repair
- Repair loop tries to access wider scope → still blocked
- Prompt injection in question → classification catches it

**Dependencies:** All previous phases
**Exit criteria:** All tests pass, no lint errors, types check clean. Safety tests cover all abort paths.

---

## Phase 10: Enhancements (Future)

Optional improvements after core is stable:

| Task | Description | Priority |
|------|-------------|----------|
| 10.1 | **LLM-based table selection** — for databases with 50+ tables | Medium |
| 10.2 | **Query caching** — cache question→SQL for repeated questions | Low |
| 10.3 | **Feedback loop** — user confirms/rejects SQL, feeds back into RAG | Medium |
| 10.4 | **Multi-turn conversations** — context across follow-up questions | Medium |
| 10.5 | **Explain mode** — return SQL + NL explanation | Low |
| 10.6 | **Cost tracking** — LLM token usage per query | Low |
| 10.7 | **Admin UI** — manage SQL examples and view query history | Low |
| 10.8 | **Semantic caching** — embed question, check similarity to cached answers | Medium |
| 10.9 | **Confidence scoring** — LLM self-rates confidence, warn user if low | Medium |

---

## Dependency Graph

```
Phase 1 (Foundation + Policy Config)
   │
   ├──▶ Phase 2 (MCP Client)  ──┐
   ├──▶ Phase 3 (LLM + Prompts) ┼──▶ Phase 5 (Nodes + Gates) ──▶ Phase 6 (Graph)
   └──▶ Phase 4 (RAG + Scope)  ─┘                                      │
                                                                        ▼
                                                               Phase 7 (API: preview/execute)
                                                                        │
                                                                        ▼
                                                               Phase 8 (Docker)
                                                                        │
                                                                        ▼
                                                               Phase 9 (Quality + Safety Tests)
```

Phases 2, 3, 4 can be developed **in parallel** after Phase 1.

---

## Key Design Decisions

1. **Production-safe from day one** — Classification, scope, and policy-aware generation are not "enhancements" — they are core nodes built in Phase 5.

2. **Agent understands policy, MCP enforces policy** — Defense in depth. Agent generates correctly (reducing MCP rejections). MCP is the hard boundary (catching anything that slips through).

3. **Preview by default** — No auto-execution. User must explicitly opt in. Reduces blast radius of bad SQL.

4. **Error classification drives repair logic** — Not all errors are repairable. Policy violations abort immediately. Only syntax/missing-column errors enter repair loop.

5. **Scoped schema retrieval** — Agent never sends full database schema to LLM. Only candidate tables. Reduces hallucination and information leakage.

6. **MCP over direct DB** — No raw psycopg2 in this project. All DB access through `postgresql-mcp-server` guardrails.

7. **ChromaDB embedded** — Lightweight, no separate server. Persists to disk. Scoped queries filter by allowed tables.

8. **LangGraph over plain LangChain** — Explicit state machine with conditional routing. Safety gates are graph edges, not middleware hacks.

9. **Multi-provider LLM** — No vendor lock-in. Switch via env var.

10. **YAML examples, version-controlled** — Reviewable, auditable. Seeded at startup. No runtime mutations to example store.
