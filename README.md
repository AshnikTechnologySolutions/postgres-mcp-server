# PostgreSQL MCP Server
![Architecture](./assets/architecture.png)

A Python MCP server for controlled agent access to PostgreSQL over STDIO, with an optional FastAPI adapter for HTTP deployments.

## What it does

- Exposes MCP tools for `health`, `uptime`, `schema`, `table_stats`, `slow_queries`, `sql_safe`, `explain_query`, `index_advisor`, `audit_logs`, and optional `sql_query`
- Uses separate read/write database roles
- Enforces read-only mode with PostgreSQL transactions, not just keyword filtering
- Reuses shared async connection pools for higher concurrency and lower latency
- Adds structured audit logging for tool calls
- Supports `pg_stat_statements` when available for slow-query analysis

## Production notes

- Prefer STDIO MCP transport for local desktop integrations.
- Keep `ALLOW_ARBITRARY_SQL=false` in production unless you fully trust the client and the write role.
- Grant the read role no write privileges at the database level.
- If you expose the FastAPI adapter, set `MCP_HTTP_API_KEY` and restrict network access to trusted callers.

## Repository structure

```text
postgres-mcp-server/
├── cli.py
├── .env.example
├── requirements.txt
├── test_client.py
└── mcp_server/
    ├── audit.py
    ├── auth.py
    ├── config.py
    ├── db.py
    ├── router.py
    ├── server.py
    ├── sql.py
    └── tools/
```

## Installation

```bash
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server
cd postgres-mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configuration

Required environment variables:

```env
DEFAULT_DB=local
ALLOW_ARBITRARY_SQL=false

LOCAL_READ_DATABASE_URL=postgresql://mcp_read:password@localhost:5432/mcp_demo
LOCAL_WRITE_DATABASE_URL=postgresql://mcp_write:password@localhost:5432/mcp_demo
REMOTE_READ_DATABASE_URL=postgresql://mcp_read:password@remote-host:5432/mcp_demo
REMOTE_WRITE_DATABASE_URL=postgresql://mcp_write:password@remote-host:5432/mcp_demo
```

Recommended PostgreSQL roles:

- `mcp_read`: `CONNECT` plus `SELECT` on approved schemas only
- `mcp_write`: narrowly scoped DML privileges for trusted automation only
- Enable `pg_stat_statements` if you want `slow_queries`

## Running the MCP server

```bash
python3 cli.py
```

Claude Desktop example:

```json
{
  "mcpServers": {
    "postgres-mcp": {
      "type": "process",
      "command": "python3",
      "args": ["cli.py"],
      "cwd": "/Users/yourname/postgres-mcp-server",
      "env": {
        "DEFAULT_DB": "local",
        "ALLOW_ARBITRARY_SQL": "false",
        "LOCAL_READ_DATABASE_URL": "postgresql://mcp_read:password@localhost:5432/mcp_demo",
        "LOCAL_WRITE_DATABASE_URL": "postgresql://mcp_write:password@localhost:5432/mcp_demo"
      }
    }
  }
}
```

## Available tools

| Tool | Purpose |
| --- | --- |
| `health` | PostgreSQL version, current DB, current user |
| `uptime` | Postmaster start time and uptime |
| `schema` | Public schema table/column metadata |
| `table_stats` | Table size and estimated row counts |
| `slow_queries` | Top queries from `pg_stat_statements` |
| `sql_safe` | Single-statement read-only SQL in a read-only transaction |
| `explain_query` | JSON `EXPLAIN` for read-only SQL |
| `index_advisor` | Simple recommendations based on the explain plan |
| `audit_logs` | Recent structured audit events with optional filters |
| `sql_query` | Optional arbitrary SQL when `ALLOW_ARBITRARY_SQL=true` |

Audit events are written to `AUDIT_LOG_PATH` as JSON Lines with:

- UTC timestamp
- tool name
- success/failure state
- transport (`mcp` or `http`)
- redacted SQL preview
- SHA-256 of the original SQL
- error text and lightweight metadata

## Optional FastAPI adapter

The repo also includes `mcp_server/router.py` for teams that want HTTP endpoints in front of the same query logic.

- Set `MCP_HTTP_API_KEY`
- Require TLS and network allow-lists
- Do not expose the write endpoint publicly

## Local verification

```bash
python3 -m py_compile cli.py mcp_server/server.py mcp_server/db.py mcp_server/sql.py mcp_server/tools/*.py mcp_server/router.py
```

## Roadmap ideas

- Add tenant-aware schema allow-lists
- Add structured audit logging sinks beyond JSONL
- Add parameterized tool variants instead of raw SQL for common operations
- Add automated tests with a disposable PostgreSQL instance
