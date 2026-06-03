# Setup & Run Guide

Step-by-step instructions to run the **text2sql-agent** + **postgresql-mcp-server** system.

---

## Architecture Overview

```
┌─────────────────────┐       HTTP (Streamable)       ┌──────────────────────────┐
│   text2sql-agent    │ ──────────────────────────────▶│  postgresql-mcp-server   │
│   (FastAPI :8080)   │   localhost:8000/mcp           │  (FastMCP :8000)         │
└─────────────────────┘                                └───────────┬──────────────┘
         │                                                         │
         │ Bedrock (embedding)                                     │ asyncpg
         ▼                                                         ▼
    AWS Bedrock                                              PostgreSQL DB
    OpenAI (LLM)                                         (banking_mcp_test)
```

---

## Prerequisites

- Python 3.12+
- PostgreSQL 14+ (running locally or remote)
- AWS credentials configured (`~/.aws/credentials`) with profile `btc-bedrock`
- OpenAI API key
- Conda (recommended) or virtualenv

---

## Step 1: Setup PostgreSQL Database

### 1.1 Create database

```bash
# Login to PostgreSQL
sudo -u postgres psql

# Create user and database
CREATE USER <your_user> WITH PASSWORD '<your_password>';
CREATE DATABASE <your_database> OWNER <your_user>;
GRANT ALL PRIVILEGES ON DATABASE <your_database> TO <your_user>;
\q
```

### 1.2 Load schema and seed data

Use the SQL files provided in `data/sql/`:

```bash
# From the postgresql-mcp-server directory (or text2sql-agent — same data)
cd /home/dungvu/workspace/code/github/postgresql-mcp-server

# Load everything at once
psql -U <your_user> -d <your_database> -f data/sql/all_in_one.sql
```

Or load files individually in order:

```bash
for f in data/sql/0*.sql data/sql/1*.sql; do
  echo "Loading $f..."
  psql -U <your_user> -d <your_database> -f "$f"
done
```

### 1.3 (Alternative) Load from CSV

```bash
cd /home/dungvu/workspace/code/github/postgresql-mcp-server
pip install psycopg2-binary
python data/scripts/load_csv_to_postgres.py
```

Environment variables for the script:
```
DATABASE_URL=postgresql://<your_user>:<your_password>@localhost:5432/<your_database>
```

---

## Step 2: Setup & Run postgresql-mcp-server

### 2.1 Create environment

```bash
cd /home/dungvu/workspace/code/github/postgresql-mcp-server

# Conda
conda create -n mcp-server python=3.12 -y
conda activate mcp-server

# Install dependencies
pip install -e .
```

### 2.2 Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` with your connection details:

```env
# ─── Connection (REQUIRED) ───────────────────────────────────────────────────
POSTGRESQL_CONNECTION_STRING="postgresql://<your_user>:<your_password>@localhost:5432/<your_database>"

# ─── Security Profile ────────────────────────────────────────────────────────
SECURITY_PROFILE=general

# ─── Write Policy ────────────────────────────────────────────────────────────
READ_ONLY=true
ENABLE_WRITE_TOOLS=false

# ─── Query Guardrails ────────────────────────────────────────────────────────
DEFAULT_LIMIT=100
MAX_LIMIT=1000

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

### 2.3 Run MCP Server

```bash
cd /home/dungvu/workspace/code/github/postgresql-mcp-server

# Run on port 8000 (default)
fastmcp run src/postgresql_mcp/app.py:mcp --transport streamable-http --port 8000
```

Verify:
```bash
curl http://localhost:8000/mcp
```

---

## Step 3: Setup & Run text2sql-agent

### 3.1 Create environment

```bash
cd /home/dungvu/workspace/code/github/text2sql-agent

# Conda
conda create -n text2sql python=3.12 -y
conda activate text2sql

# Install dependencies
pip install -e .
```

### 3.2 Configure `.env`

```env
# ─── MCP Server ───────────────────────────────────────────────────────────────
MCP_BACKEND=postgresql
POSTGRESQL_MCP_SERVER_URL=http://localhost:8000/mcp

# ─── LLM (OpenAI for generation) ──────────────────────────────────────────────
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=<your-openai-api-key>
LLM_TEMPERATURE=0.0

# ─── AWS Bedrock (for embedding & reranker) ──────────────────────────────────
AWS_REGION=us-east-1
AWS_PROFILE=btc-bedrock

# ─── Embedding (Bedrock) ──────────────────────────────────────────────────────
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSIONS=1024

# ─── Reranker ─────────────────────────────────────────────────────────────────
RERANKER_ENABLED=false
RERANKER_MODEL_ID=cohere.rerank-v3-5:0
RERANKER_TOP_K=5

# ─── ChromaDB ─────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR=./data/chroma

# ─── RAG ──────────────────────────────────────────────────────────────────────
RAG_TOP_K=10
RAG_SCHEMA_COLLECTION=schema_descriptions
RAG_EXAMPLES_COLLECTION=sql_examples

# ─── Agent Behavior ───────────────────────────────────────────────────────────
MAX_REPAIR_ATTEMPTS=3
DEFAULT_EXECUTE=false

# ─── Schema Scope ─────────────────────────────────────────────────────────────
TABLE_ALLOWLIST=
SCHEMA_NAME=public

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

### 3.3 Seed RAG data (ChromaDB)

On first run, you need to seed schema descriptions and SQL examples into ChromaDB:

```bash
cd /home/dungvu/workspace/code/github/text2sql-agent
python -m text2sql_agent.rag.seed
```

### 3.4 Run text2sql-agent

```bash
cd /home/dungvu/workspace/code/github/text2sql-agent
uvicorn text2sql_agent.main:app --host 0.0.0.0 --port 8080 --reload
```

Verify:
```bash
curl http://localhost:8080/health
```

Expected response:
```json
{"status": "ok", "mcp_server": "http://localhost:8000/mcp", "mcp_connected": true}
```

---

## Step 4: Verify End-to-End

```bash
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me the 5 most recent customers"}'
```

---

## Step 5: Run Advanced Test Suite

The project includes a comprehensive E2E test suite at `tests/manual/test_agent_advanced.py` that covers multi-table joins, time-series aggregation, policy enforcement, security, and Vietnamese banking terminology.

**Prerequisites:** Both MCP server (port 8000) and text2sql-agent (port 8001) must be running.

### 5.1 Run all tests

```bash
cd /home/dungvu/workspace/code/github/text2sql-agent
python tests/manual/test_agent_advanced.py
```

### 5.2 Run with verbose output

```bash
python tests/manual/test_agent_advanced.py -v
```

### 5.3 Run a specific category

Available categories: `multi_join`, `time_series`, `aggregation`, `subquery`, `policy`, `vietnamese`, `edge_case`, `security`

```bash
python tests/manual/test_agent_advanced.py --category multi_join
python tests/manual/test_agent_advanced.py --category security
```

### 5.4 Run a single test by ID

```bash
python tests/manual/test_agent_advanced.py --id join-01
```

### 5.5 Run with query execution (also hits /query/execute)

```bash
python tests/manual/test_agent_advanced.py --execute
```

### 5.6 View last test report

```bash
python tests/manual/test_agent_advanced.py --report
```

Results are saved as timestamped JSON in `tests/results/`.

### 5.7 Custom agent URL

If the agent runs on a different port:

```bash
python tests/manual/test_agent_advanced.py --base-url http://127.0.0.1:8080
```

---

## Startup Order (Summary)

```
1. PostgreSQL DB          (must be running first)
2. postgresql-mcp-server  (port 8000, connects to DB)
3. text2sql-agent         (port 8080, connects to MCP server)
```

---

## Docker Deployment

As an alternative to running services manually, you can use Docker to bring up the entire stack with a single command.

### Option A: Docker Compose (full stack)

Starts PostgreSQL + MCP server + text2sql-agent together:

```bash
cd /home/dungvu/workspace/code/github/text2sql-agent

# Set required credentials in .env:
#   LLM_API_KEY=<your-openai-key>
#   AWS_ACCESS_KEY_ID=<your-aws-access-key>
#   AWS_SECRET_ACCESS_KEY=<your-aws-secret-key>

# Build and start all services
docker compose up --build
```

Services will start in order:
1. `postgres` (port 5432) — auto-seeds schema from `data/sql/all_in_one.sql`
2. `mcp-server` (port 8000) — waits for postgres to be healthy
3. `agent` (port 8080) — waits for mcp-server to be healthy

Stop everything:
```bash
docker compose down
```

Remove volumes (reset database + ChromaDB):
```bash
docker compose down -v
```

### Option B: Standalone agent image

If MCP server and PostgreSQL are already running elsewhere:

```bash
# Build
docker build -t text2sql-agent .

# Run (pass env vars for external services)
docker run -p 8080:8080 \
  -e POSTGRESQL_MCP_SERVER_URL=http://host.docker.internal:8000/mcp \
  -e LLM_API_KEY=<your-openai-key> \
  -e AWS_ACCESS_KEY_ID=<your-aws-access-key> \
  -e AWS_SECRET_ACCESS_KEY=<your-aws-secret-key> \
  -e AWS_REGION=us-east-1 \
  -e EMBEDDING_PROVIDER=bedrock \
  text2sql-agent
```

### Seed RAG in Docker

On first run, seed ChromaDB inside the container:

```bash
docker compose exec agent python -m text2sql_agent.rag.seed
```

### Docker environment variables

In Docker, AWS credentials are passed via env vars (not profile file):

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | OpenAI API key |
| `AWS_ACCESS_KEY_ID` | AWS access key for Bedrock |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for Bedrock |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `POSTGRES_USER` | DB user (default: `postgres`) |
| `POSTGRES_PASSWORD` | DB password (default: `postgres`) |
| `POSTGRES_DB` | DB name (default: `banking_mcp`) |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `mcp_connected: false` | Ensure postgresql-mcp-server is running on port 8000 |
| DB connection failed | Check PostgreSQL is running, verify user/password |
| Embedding error | Verify AWS credentials: `aws sts get-caller-identity --profile btc-bedrock` |
| OpenAI 401 | Check `LLM_API_KEY` in `.env` |
| ChromaDB empty | Re-run `python -m text2sql_agent.rag.seed` |

---

## AWS Credentials Setup

If you don't have the AWS profile `btc-bedrock` configured yet:

```bash
# ~/.aws/credentials
[btc-bedrock]
aws_access_key_id = <your_access_key>
aws_secret_access_key = <your_secret_key>

# ~/.aws/config
[profile btc-bedrock]
region = us-east-1
```

Verify:
```bash
aws sts get-caller-identity --profile btc-bedrock
```
