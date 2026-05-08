#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOKI_CONFIG="$ROOT_DIR/deployment/loki/loki.local.yaml"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
LOKI_IMAGE="${LOKI_IMAGE:-grafana/loki:3.5.5}"

if [[ -d "$DOCKER_DESKTOP_BIN" ]]; then
  export PATH="$DOCKER_DESKTOP_BIN:$PATH"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI is not installed" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not running" >&2
  echo "Start Docker Desktop first, then rerun this script." >&2
  exit 1
fi

docker rm -f loki-local >/dev/null 2>&1 || true

docker run --name loki-local \
  -p 3100:3100 \
  -v "$LOKI_CONFIG:/etc/loki/local-config.yaml:ro" \
  "$LOKI_IMAGE" \
  -config.file=/etc/loki/local-config.yaml
