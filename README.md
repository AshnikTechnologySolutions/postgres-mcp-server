# PostgreSQL MCP Server
![Architecture](./assets/architecture.png)

Secure MCP access to PostgreSQL for Claude Desktop and other MCP clients, with read-only enforcement, pooled async connections, audit logging, and separate local/remote database targets.

## Highlights

- MCP tools for `health`, `uptime`, `schema`, `table_stats`, `slow_queries`, `sql_safe`, `explain_query`, `index_advisor`, `audit_logs`, and optional `sql_query`
- separate read and write database roles
- read-only execution enforced with PostgreSQL transactions
- shared `asyncpg` pools for better concurrency and lower latency
- structured audit logging for tool calls
- Claude Desktop setup without putting DB credentials in `claude_desktop_config.json`

## Quick start

```bash
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server
cd postgres-mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.claude.local
cp .env.example .env.claude.remote
```

Update `.env.claude.local` and `.env.claude.remote` with your real credentials, then run:

```bash
./venv/bin/python cli.py
```

For a full setup and operations guide, see [RUNBOOK.md](./RUNBOOK.md).

## Why this exists

This project gives AI agents controlled access to PostgreSQL through MCP instead of handing them raw network/database access. The focus is production-minded operation:

- least-privilege read and write roles
- safer read-only SQL access
- explain-plan and index-advice tooling
- audit visibility into tool usage
- support for both local and remote database targets

## Repository structure

```text
postgres-mcp-server/
├── cli.py
├── .env.example
├── requirements.txt
├── scripts/
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

## Configuration

Core settings:

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
- enable `pg_stat_statements` if you want `slow_queries`

Claude-specific env files:

- `.env.claude.local`: local database target
- `.env.claude.remote`: remote database target
- both are ignored by git because of `.env.*`

Useful optional settings:

```env
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=20
DB_CONNECT_TIMEOUT_SECONDS=5
AUDIT_LOG_PATH=mcp_audit.log
AUDIT_LOG_MAX_QUERY_PREVIEW=240
MCP_HTTP_API_KEY=change-me
```

## Claude Desktop setup

The recommended setup is to keep credentials in local env files and let Claude Desktop call launcher scripts.

Launcher scripts:

- `scripts/run_claude_local.sh`
- `scripts/run_claude_remote.sh`

Each script:

- loads a private env file
- uses the repo virtualenv at `venv/bin/python`
- starts `cli.py` over STDIO

Example `.env.claude.local`:

```env
DEFAULT_DB=local
ALLOW_ARBITRARY_SQL=false
LOCAL_READ_DATABASE_URL=postgresql://mcp_read:password@localhost:5432/mcp_demo
LOCAL_WRITE_DATABASE_URL=postgresql://mcp_write:password@localhost:5432/mcp_demo
```

Example `.env.claude.remote`:

```env
DEFAULT_DB=remote
ALLOW_ARBITRARY_SQL=false
REMOTE_READ_DATABASE_URL=postgresql://mcp_read:password@remote-host:5432/mcp_demo
REMOTE_WRITE_DATABASE_URL=postgresql://mcp_write:password@remote-host:5432/mcp_demo
```

Example Claude Desktop config:

```json
{
  "mcpServers": {
    "postgres-mcp-local": {
      "type": "process",
      "command": "/Users/yourname/postgres-mcp-server/scripts/run_claude_local.sh",
      "cwd": "/Users/yourname/postgres-mcp-server"
    },
    "postgres-mcp-remote": {
      "type": "process",
      "command": "/Users/yourname/postgres-mcp-server/scripts/run_claude_remote.sh",
      "cwd": "/Users/yourname/postgres-mcp-server"
    }
  }
}
```

This keeps secrets out of `claude_desktop_config.json`.

## Available tools

| Tool | Purpose |
| --- | --- |
| `health` | PostgreSQL version, current DB, current user |
| `uptime` | Postmaster start time and uptime |
| `schema` | Public schema table and column metadata |
| `table_stats` | Table size and estimated row counts |
| `slow_queries` | Top queries from `pg_stat_statements` |
| `sql_safe` | Single-statement read-only SQL in a read-only transaction |
| `explain_query` | JSON `EXPLAIN` for read-only SQL |
| `index_advisor` | Simple recommendations based on the plan |
| `audit_logs` | Recent structured audit events with optional filters |
| `sql_query` | Optional arbitrary SQL when `ALLOW_ARBITRARY_SQL=true` |

## Audit logging

Audit events are written to `AUDIT_LOG_PATH` as JSON Lines and include:

- UTC timestamp
- tool name
- success or failure state
- transport (`mcp` or `http`)
- redacted SQL preview
- SHA-256 of the original SQL
- error text and lightweight metadata

## Security notes

- Prefer `sql_safe` and keep `ALLOW_ARBITRARY_SQL=false` in production.
- Enforce least privilege at the database role level, not just in Python.
- Keep read-only and write credentials separate.
- If you expose the FastAPI adapter, require `MCP_HTTP_API_KEY`, TLS, and network allow-lists.

## Optional FastAPI adapter

The repo also includes `mcp_server/router.py` for teams that want HTTP endpoints in front of the same query logic.

- protect it with `MCP_HTTP_API_KEY`
- require TLS
- restrict network access
- avoid exposing write endpoints publicly

## Local verification

```bash
python3 -m py_compile cli.py mcp_server/server.py mcp_server/db.py mcp_server/sql.py mcp_server/tools/*.py mcp_server/router.py
python3 test_client.py
```

## Roadmap

- tenant-aware schema allow-lists
- audit sinks beyond JSONL
- parameterized tool variants instead of raw SQL for common operations
- automated tests with a disposable PostgreSQL instance

## Changelog

Project release notes are tracked in [CHANGELOG.md](./CHANGELOG.md).

## Contributing

Contribution guidance lives in [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE).
