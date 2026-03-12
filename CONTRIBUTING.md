# Contributing

Thanks for contributing to `postgres-mcp-server`.

## Before opening a PR

- Open an issue first for major changes
- Keep changes focused and easy to review
- Prefer production-safe defaults
- Avoid exposing database credentials in docs, code samples, or config examples

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Verification

Run at least:

```bash
python3 -m py_compile cli.py mcp_server/server.py mcp_server/db.py mcp_server/sql.py mcp_server/tools/*.py mcp_server/router.py
```

If your change touches Claude Desktop integration, verify the launcher scripts and env-file flow still work.

## Guidelines

- Keep read-only behavior strict
- Prefer least-privilege database access
- Keep MCP stdio output clean and protocol-safe
- Update `README.md` when user-facing setup changes
- Add an entry to `CHANGELOG.md` for notable changes
