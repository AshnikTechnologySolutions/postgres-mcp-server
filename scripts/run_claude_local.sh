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

exec "$PYTHON_BIN" cli.py
