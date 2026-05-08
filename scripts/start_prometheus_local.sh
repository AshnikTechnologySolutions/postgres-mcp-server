#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROMETHEUS_CONFIG="$ROOT_DIR/deployment/prometheus/prometheus.local.yaml"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
PROMETHEUS_IMAGE="${PROMETHEUS_IMAGE:-prom/prometheus:v3.5.0}"

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

docker rm -f prometheus-local >/dev/null 2>&1 || true

docker run --name prometheus-local \
  -p 9090:9090 \
  -v "$PROMETHEUS_CONFIG:/etc/prometheus/prometheus.yml:ro" \
  "$PROMETHEUS_IMAGE" \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.enable-remote-write-receiver
