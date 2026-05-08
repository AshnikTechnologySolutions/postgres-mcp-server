#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROMTAIL_CONFIG="$ROOT_DIR/deployment/promtail/promtail.local.yaml"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
PROMTAIL_IMAGE="${PROMTAIL_IMAGE:-grafana/promtail:3.5.5}"

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

docker rm -f promtail-local >/dev/null 2>&1 || true

docker run --name promtail-local \
  -p 9080:9080 \
  -v "$PROMTAIL_CONFIG:/etc/promtail/config.yml:ro" \
  -v "$ROOT_DIR:/workspace:ro" \
  "$PROMTAIL_IMAGE" \
  -config.file=/etc/promtail/config.yml
