> **Official repository maintained by Ashnik Technology Solutions Pvt Ltd**

# PostgreSQL MCP Server
### Ashnik Secure MCP Bridge For PostgreSQL

| Local | Production |
|---|---|
| ![Local architecture](./assets/architecture-local.svg) | ![Production architecture](./assets/architecture-production.svg) |

A secure **Model Context Protocol (MCP)** server for PostgreSQL that enables AI assistants such as Claude Desktop and other MCP clients to safely query PostgreSQL databases using controlled read-only access and secure connection handling.

## Status

This project is production-oriented and can be deployed for controlled internal production use when you pair it with:

- least-privilege PostgreSQL roles
- TLS and auth at the HTTP edge
- centralized observability
- deployment-specific secret management

It already includes strong operational foundations:

- read-only query enforcement for safe tools
- separate read and write database roles
- shared async connection pools
- audit logging
- Claude Desktop integration without inline database credentials

For broad, regulated, or multi-tenant production workloads, we still recommend adding:

- schema, table, and column allow-lists
- response redaction for sensitive data
- secret-manager integration
- automated tests and deployment checks
- credential rotation without restart

## Highlights

- MCP tools for `health`, `uptime`, `schema`, `table_stats`, `slow_queries`, `sql_safe`, `explain_query`, `index_advisor`, `audit_logs`, `readiness`, `config_status`, `audit_summary`, `access_scope`, `pool_status`, `locks`, `index_usage`, `vacuum_status`, `replication_status`, `redaction_test`, and optional `sql_query`
- separate read and write database roles
- read-only execution enforced with PostgreSQL transactions
- shared `asyncpg` pools for better concurrency and lower latency
- structured audit logging for tool calls
- request ID correlation across HTTP responses, spans, and audit logs
- Claude Desktop setup without putting DB credentials in `claude_desktop_config.json`
- HTTP deployment starter for NGINX and observability wiring

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
For production deployment (NGINX, TLS, pg_stat_statements, API reference), see [DEPLOYMENT.md](./DEPLOYMENT.md).
For the current runtime and deployment architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md).
For HTTP proxy and telemetry setup, see [deployment/observability/README.md](./deployment/observability/README.md).
For the exact local Grafana/Tempo/Collector test flow, see [deployment/observability/LOCAL_INTEGRATION_TEST.md](./deployment/observability/LOCAL_INTEGRATION_TEST.md).
For starter Grafana dashboards, see [deployment/grafana/README.md](./deployment/grafana/README.md).

Important distinction:

- the files under `deployment/*local*` and the `scripts/start_*_local.sh` helpers are for local Docker Desktop validation
- production deployment should use environment-specific hostnames, storage paths, TLS, and secret management rather than the local starter values

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
├── tests/
├── test_client.py
└── mcp_server/
    ├── audit.py
    ├── auth.py
    ├── config.py
    ├── db.py
    ├── http_app.py
    ├── otel.py
    ├── request_context.py
    ├── router.py
    ├── server.py
    ├── sql.py
    └── tools/
        ├── ops.py
        └── ...
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
MAX_RESULT_ROWS=2000
OTEL_ENABLED=false
OTEL_SERVICE_NAME=postgres-mcp-server
OTEL_SERVICE_VERSION=1.0.0
OTEL_ENVIRONMENT=development
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
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
- can export STDIO MCP spans when `OTEL_ENABLED=true`

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
| `readiness` | Operational readiness checks for DB connectivity and extensions |
| `config_status` | Safe runtime configuration summary without secrets |
| `audit_summary` | Aggregated audit activity, failures, and common errors |
| `access_scope` | Schemas and tables visible to the active read role |
| `pool_status` | Async connection pool configuration and utilization snapshot |
| `locks` | Blocked sessions, blockers, and lock wait details |
| `index_usage` | Index scans, size, and low-usage or unused indexes |
| `vacuum_status` | Vacuum/analyze activity and dead tuple pressure by table |
| `replication_status` | Replica, slot, and recovery status for PostgreSQL replication |
| `redaction_test` | Sample masking test for emails, phones, SSNs, and payment cards |
| `sql_query` | Optional arbitrary SQL when `ALLOW_ARBITRARY_SQL=true` |

## Audit logging

Audit events are written to `AUDIT_LOG_PATH` as JSON Lines and include:

- UTC timestamp
- tool name
- success or failure state
- transport (`mcp` or `http`)
- request ID
- trace ID and span ID when tracing is active
- redacted SQL preview
- SHA-256 of the original SQL
- error text and lightweight metadata

## Security notes

- Prefer `sql_safe` and keep `ALLOW_ARBITRARY_SQL=false` in production.
- Enforce least privilege at the database role level, not just in Python.
- Keep read-only and write credentials separate.
- If you expose the HTTP adapter, require `MCP_HTTP_API_KEY`, TLS, and network allow-lists.

## HTTP deployment

The repo includes a FastAPI HTTP adapter (`mcp_server/http_app.py`) for teams that want to expose the same query logic over HTTPS — useful for Claude Code, REST clients, and multi-user deployments behind NGINX.

- protect it with `MCP_HTTP_API_KEY`
- require TLS
- restrict network access
- avoid exposing write endpoints publicly

HTTP app entrypoint:

```bash
uvicorn mcp_server.http_app:app --host 127.0.0.1 --port 8000
```

Deployment starter files:

- `deployment/nginx/mcp-http.conf`
- `deployment/otel/otel-collector.yaml`
- `deployment/observability/README.md`
- `deployment/observability/LOCAL_INTEGRATION_TEST.md`

With OTel enabled:

- FastAPI requests are traced through the HTTP app
- STDIO MCP tool invocations from Claude Desktop are traced through the MCP server
- shared PostgreSQL execution helpers emit DB spans
- traces export to the OTLP HTTP endpoint you configure
- local starter scripts support Tempo, Prometheus, Loki, and Promtail for a single-machine test stack

## Local verification

```bash
python3 -m py_compile cli.py mcp_server/server.py mcp_server/db.py mcp_server/sql.py mcp_server/http_app.py mcp_server/otel.py mcp_server/request_context.py mcp_server/router.py mcp_server/tools/*.py
python3 test_client.py
```

Unit tests (no database required):

```bash
./venv/bin/python -m pytest tests/ -v --ignore=tests/test_integration.py
```

Integration tests (requires a local PostgreSQL instance with `LOCAL_READ_DATABASE_URL` set):

```bash
./venv/bin/python -m pytest tests/test_integration.py -v
```

## Roadmap

- tenant-aware schema allow-lists
- audit sinks beyond JSONL
- parameterized tool variants instead of raw SQL for common operations
- CI pipeline with a disposable PostgreSQL instance for automated integration testing

## Changelog

Release history and notable changes are documented in the
[CHANGELOG.md](./CHANGELOG.md).

Each release describes:

- new features
- security improvements
- performance enhancements
- bug fixes
- breaking changes (if any)

We recommend reviewing the changelog before upgrading between versions.


## Contributing

Contributions from the community are welcome.

You can contribute in several ways:

- reporting issues
- proposing improvements
- submitting pull requests
- improving documentation
- suggesting security or operational enhancements

Before contributing, please review the contribution guidelines in  
[CONTRIBUTING.md](./CONTRIBUTING.md).

### Development workflow

Typical contribution flow:

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commit messages
4. Add tests or documentation if applicable
5. Submit a pull request

All pull requests are reviewed by project maintainers.

### Governance

Project governance and stewardship are described in  
[GOVERNANCE.md](./GOVERNANCE.md).


## License

This project is licensed under the **Apache License 2.0**.

See the full license text in the  
[LICENSE](./LICENSE) file.

Copyright © Ashnik Technology Solutions Pvt Ltd.

Unless otherwise stated, all contributions to this repository are
distributed under the same license.
