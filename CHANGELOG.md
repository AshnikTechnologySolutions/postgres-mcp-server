# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-05-08

### Added

**MCP tools**
- `readiness` — DB connectivity and extension health check; degrades gracefully when `pg_stat_statements` is absent
- `config_status` — safe runtime configuration summary (no secrets exposed)
- `audit_summary` — aggregated audit activity, failure counts, and top errors
- `access_scope` — schemas and tables visible to the active read role
- `pool_status` — async connection pool configuration and utilization snapshot
- `locks` — blocked sessions, blockers, and lock wait details from `pg_stat_activity`
- `index_usage` — index scan counts, sizes, and unused/low-usage classification
- `vacuum_status` — vacuum/analyze activity and dead tuple pressure by table
- `replication_status` — replica state, replication slots, and WAL position
- `redaction_test` — sample masking for emails, phones, SSNs, and payment card numbers

**HTTP adapter**
- FastAPI HTTP adapter (`mcp_server/http_app.py`) exposing all MCP tools as REST endpoints
- API key authentication via `MCP_HTTP_API_KEY` for HTTP routes
- NGINX starter config for TLS termination and rate limiting (`deployment/nginx/`)
- `/healthz` and `/readyz` endpoints for load-balancer and orchestrator probes

**Observability**
- OpenTelemetry tracing (`mcp_server/otel.py`) for FastAPI requests and PostgreSQL execution spans
- Request ID correlation across HTTP response headers, OTel spans, and audit log entries (`mcp_server/request_context.py`)
- OTel Collector, Tempo, Prometheus, Loki, and Promtail starter configs (`deployment/`)
- Local Docker Desktop observability walkthrough (`deployment/observability/LOCAL_INTEGRATION_TEST.md`)
- Grafana dashboard for request rates, latency, error rates, and DB pool metrics (`deployment/grafana/`)

**Testing and CI**
- 38-test unit suite covering SQL validation, audit logging, ops tools, OTel init, HTTP app, and server tracing
- Integration test suite (39 tests) against a live local PostgreSQL instance with `unittest.IsolatedAsyncioTestCase`
- GitHub Actions CI workflow running syntax check, lint, and unit tests on every push and PR
- `requirements-dev.txt` for isolated dev/test dependency installation

**Developer tooling**
- `pyproject.toml` with ruff linter config (line-length 130, explicit rule set, per-file ignores)
- Architecture diagrams for local STDIO and production HTTP deployment paths (`assets/`)

**Documentation**
- `DEPLOYMENT.md` — production deployment guide (NGINX/TLS, pg_stat_statements, API reference, Claude integration)
- `ARCHITECTURE.md` — runtime architecture overview for both STDIO and HTTP modes
- `RUNBOOK.md` — full setup, operations, verification, and troubleshooting guide

### Changed
- `readiness` check now returns `ok: true` with `status: degraded` when `pg_stat_statements` is missing — only database connectivity gates the probe; missing optional extensions no longer cause false 503s
- `EXPLAIN FORMAT JSON` output correctly parsed from asyncpg raw string to Python list before returning to callers
- `index_usage` query column references qualified with table aliases after JOIN with `pg_index` to fix ambiguous column error
- Claude Desktop launcher scripts updated to support optional OTel span export via `OTEL_ENABLED=true`
- Structured audit logging expanded to include request ID, trace ID, span ID, redacted SQL preview, and SHA-256 query hash

### Security
- Read-only SQL enforcement via PostgreSQL `SET TRANSACTION READ ONLY` inside `asyncpg` transactions — write attempts raise `ReadOnlySQLTransactionError` at the database level
- API key authentication required for all HTTP endpoints when `MCP_HTTP_API_KEY` is set
- Database credentials kept out of `claude_desktop_config.json` via private `.env.claude.*` launcher files
- Audit log records every tool call with success/failure state, transport, and error text
- `ALLOW_ARBITRARY_SQL` defaults to `false`; write-capable `sql_query` tool is opt-in only

## [0.1.0] — 2025-04

### Added
- `health`, `uptime`, `schema`, `table_stats`, `slow_queries`, `sql_safe`, `explain_query`, `index_advisor`, `audit_logs`, `sql_query` MCP tools
- Separate read and write database roles with dedicated `asyncpg` connection pools
- Structured audit logging (JSONL) for all tool invocations
- Claude Desktop launcher scripts for local and remote PostgreSQL targets
- Private `.env.claude.*` workflow to keep credentials out of Claude config
