# Runbook

This runbook explains how to install, configure, operate, and troubleshoot `postgres-mcp-server`.

## 1. Purpose

Use this repository when you want an MCP server to give Claude Desktop or another MCP client controlled access to PostgreSQL.

Primary goals:

- keep database credentials out of Claude Desktop config
- use read-only access by default
- support both local and remote PostgreSQL targets
- provide audit visibility for tool usage

## 2. Prerequisites

You need:

- macOS or Linux shell access
- Python 3
- PostgreSQL credentials for dedicated read and optional write roles
- Claude Desktop if you want desktop MCP integration

Recommended database roles:

- `mcp_read`: read-only access to approved schemas/views
- `mcp_write`: narrow write access only if required

Do not use a PostgreSQL superuser.

## 3. Repository layout

Important files:

- `cli.py`: MCP server entrypoint
- `mcp_server/server.py`: MCP tool registration and server logic
- `mcp_server/db.py`: async PostgreSQL pool management
- `mcp_server/sql.py`: shared SQL validation and execution helpers
- `mcp_server/audit.py`: audit log writer and reader
- `scripts/run_claude_local.sh`: Claude launcher for the local DB target
- `scripts/run_claude_remote.sh`: Claude launcher for the remote DB target
- `.env.example`: example environment variables

## 4. Initial setup

Clone and prepare the virtual environment:

```bash
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server
cd postgres-mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create local secret files:

```bash
cp .env.example .env.claude.local
cp .env.example .env.claude.remote
chmod 600 .env.claude.local .env.claude.remote
```

## 5. Environment configuration

### Local target

Edit `.env.claude.local`:

```env
DEFAULT_DB=local
ALLOW_ARBITRARY_SQL=false
LOCAL_READ_DATABASE_URL=postgresql://mcp_read:password@localhost:5432/mcp_demo
LOCAL_WRITE_DATABASE_URL=postgresql://mcp_write:password@localhost:5432/mcp_demo
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=20
DB_CONNECT_TIMEOUT_SECONDS=5
AUDIT_LOG_PATH=mcp_audit.log
AUDIT_LOG_MAX_QUERY_PREVIEW=240
```

### Remote target

Edit `.env.claude.remote`:

```env
DEFAULT_DB=remote
ALLOW_ARBITRARY_SQL=false
REMOTE_READ_DATABASE_URL=postgresql://mcp_read:password@db-host:5432/mcp_demo
REMOTE_WRITE_DATABASE_URL=postgresql://mcp_write:password@db-host:5432/mcp_demo
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=20
DB_CONNECT_TIMEOUT_SECONDS=5
AUDIT_LOG_PATH=mcp_audit.log
AUDIT_LOG_MAX_QUERY_PREVIEW=240
```

Optional HTTP setting:

```env
MCP_HTTP_API_KEY=change-me
```

## 6. Local server startup

Run directly:

```bash
./venv/bin/python cli.py
```

This starts the MCP server over STDIO.

## 7. Claude Desktop setup

The recommended Claude Desktop pattern is to call the launcher scripts instead of embedding database credentials inside `claude_desktop_config.json`.

Example config:

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

Launcher behavior:

- loads `.env.claude.local` or `.env.claude.remote`
- uses `venv/bin/python`
- starts `cli.py`

After updating Claude Desktop config, restart Claude Desktop.

## 8. Supported tools

Available MCP tools:

- `health`
- `uptime`
- `schema`
- `table_stats`
- `slow_queries`
- `sql_safe`
- `explain_query`
- `index_advisor`
- `audit_logs`
- `sql_query` when `ALLOW_ARBITRARY_SQL=true`

Tool guidance:

- use `sql_safe` for normal querying
- use `explain_query` to inspect plans safely
- use `index_advisor` for first-pass tuning guidance
- keep `sql_query` disabled in production unless there is a strong operational reason

## 9. Example usage in Claude

Example prompts:

- `Show database health`
- `List tables and columns in the schema`
- `Run a safe query: SELECT * FROM customers LIMIT 10`
- `Explain this query: SELECT * FROM orders WHERE customer_id = 42`
- `Show the last 20 audit log events`
- `Show slow queries`

## 10. Audit logging

Audit logs are written to `AUDIT_LOG_PATH`, which defaults to:

```text
mcp_audit.log
```

Each event includes:

- timestamp
- tool name
- success/failure
- transport
- redacted SQL preview
- query hash
- error/details metadata

Inspect audit logs directly:

```bash
tail -n 20 mcp_audit.log
```

Or through MCP:

- `Show the last 20 audit log events`
- `Show failed audit log events`
- `Show audit logs for sql_safe`

## 11. Security controls

Use these controls in production:

- keep `ALLOW_ARBITRARY_SQL=false`
- grant the MCP role access only to approved schemas or views
- do not give the MCP server superuser credentials
- prefer masked views for PII/PHI
- separate read and write credentials
- protect the optional HTTP adapter with `MCP_HTTP_API_KEY`, TLS, and network allow-lists

Important note:

This repository enforces read-only behavior for safe tools, but the strongest control is still PostgreSQL permissions. If the DB role can read sensitive data, the MCP server can read it too.

## 12. Credential rotation

Current operational guidance:

1. Rotate the database password in PostgreSQL.
2. Update `.env.claude.local` or `.env.claude.remote`.
3. Restart Claude Desktop or restart the MCP server process.

Reason:

- database pools reuse existing connections
- a restart ensures new credentials are used consistently

## 13. Verification steps

Syntax verification:

```bash
python3 -m py_compile cli.py mcp_server/server.py mcp_server/db.py mcp_server/sql.py mcp_server/tools/*.py mcp_server/router.py
```

Dependency verification:

```bash
./venv/bin/python -c "import asyncpg, fastmcp; print('dependencies_ok')"
```

Basic launcher verification:

```bash
zsh -lc 'set -a; source ./.env.claude.local; set +a; ./venv/bin/python -c "from mcp_server.server import mcp; print(\"local_import_ok\")"'
zsh -lc 'set -a; source ./.env.claude.remote; set +a; ./venv/bin/python -c "from mcp_server.server import mcp; print(\"remote_import_ok\")"'
```

Interactive test client:

```bash
python3 test_client.py
```

## 14. Troubleshooting

### `ModuleNotFoundError: asyncpg`

Cause:

- Claude or the shell is using the wrong Python interpreter

Fix:

- make sure the launcher scripts use `venv/bin/python`
- reinstall dependencies if needed:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Claude says server disconnected

Check:

- the launcher script path in Claude config
- the repo `cwd`
- whether `.env.claude.local` or `.env.claude.remote` exists
- whether the DB credentials are valid

### `Missing .env.claude.local` or `Missing .env.claude.remote`

Create the env file from `.env.example` and add the real credentials.

### PostgreSQL authentication errors

Check:

- host, port, database name
- username/password
- pg_hba.conf rules
- firewall or network rules

### `pg_stat_statements` errors

Enable the extension if you want `slow_queries`:

```sql
CREATE EXTENSION pg_stat_statements;
```

### No audit logs appearing

Check:

- `AUDIT_LOG_PATH`
- file permissions in the repo directory
- whether tools are actually being invoked through MCP

## 15. Operational checklist

Before go-live:

- configure dedicated `mcp_read` and `mcp_write` roles
- set `ALLOW_ARBITRARY_SQL=false`
- use private `.env.claude.*` files
- verify Claude launcher scripts work
- test `health`, `schema`, `sql_safe`, and `audit_logs`
- confirm audit logs are being written
- restrict or disable the HTTP adapter unless required

## 16. Recommended next hardening steps

- add schema/table/column allow-lists
- add response redaction for PII patterns
- add pool refresh support for secret rotation
- split audit logs per environment
- move secrets to a secret manager or macOS Keychain
