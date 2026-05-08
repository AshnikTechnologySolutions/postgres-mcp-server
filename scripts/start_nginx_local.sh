#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NGINX_CONFIG="$ROOT_DIR/deployment/nginx/mcp-http.local.docker.conf"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:1.27-alpine}"

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

docker rm -f nginx-mcp-local >/dev/null 2>&1 || true

exec docker run --name nginx-mcp-local \
  -p 8081:8081 \
  -v "$NGINX_CONFIG:/etc/nginx/nginx.conf:ro" \
  "$NGINX_IMAGE"
