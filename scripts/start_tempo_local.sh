#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPO_CONFIG="$ROOT_DIR/deployment/otel/tempo.local.yaml"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
TEMPO_IMAGE="${TEMPO_IMAGE:-grafana/tempo:2.10.3}"
TEMPO_REMOTE_WRITE_URL="${TEMPO_REMOTE_WRITE_URL:-http://host.docker.internal:9090/api/v1/write}"

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

docker rm -f tempo-local >/dev/null 2>&1 || true

docker run --name tempo-local \
  -p 3200:3200 \
  -p 14317:4317 \
  -p 14318:4318 \
  -e "TEMPO_REMOTE_WRITE_URL=$TEMPO_REMOTE_WRITE_URL" \
  -v "$TEMPO_CONFIG:/etc/tempo.yaml:ro" \
  "$TEMPO_IMAGE" \
  -config.file=/etc/tempo.yaml \
  -config.expand-env=true
