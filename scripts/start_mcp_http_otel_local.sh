#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.claude.local"
PYTHON_BIN="$ROOT_DIR/venv/bin/python"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing $PYTHON_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
set -a
source "$ENV_FILE"
set +a

export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=postgres-mcp-server
export OTEL_ENVIRONMENT=local
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces

exec "$PYTHON_BIN" -m uvicorn mcp_server.http_app:app --host 127.0.0.1 --port 8000
