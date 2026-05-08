#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COLLECTOR_CONFIG="$ROOT_DIR/deployment/otel/otel-collector.local.yaml"
OTELCOL_BIN="${OTELCOL_BIN:-}"

if [[ -z "$OTELCOL_BIN" ]]; then
  OTELCOL_BIN="$(command -v otelcol-contrib 2>/dev/null || true)"
fi

if [[ -z "$OTELCOL_BIN" && -x "$HOME/.local/bin/otelcol-contrib" ]]; then
  OTELCOL_BIN="$HOME/.local/bin/otelcol-contrib"
fi

if [[ ! -x "$OTELCOL_BIN" ]]; then
  echo "Unable to find otelcol-contrib in PATH or at $HOME/.local/bin/otelcol-contrib" >&2
  exit 1
fi

exec "$OTELCOL_BIN" --config "$COLLECTOR_CONFIG"
