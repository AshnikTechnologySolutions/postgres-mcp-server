# PostgreSQL MCP Server — Production Deployment Guide

**Audience:** DBAs, platform engineers, DevOps, cloud architects  
**Transport:** HTTP mode (STDIO is local-dev only)  
**Architecture:** `Claude / AI Client → NGINX (TLS) → MCP Server → PostgreSQL`

### Architecture diagrams

| Local development | Production |
|---|---|
| ![Local architecture](assets/architecture-local.svg) | ![Production architecture](assets/architecture-production.svg) |

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [PostgreSQL Server Setup](#2-postgresql-server-setup)
3. [Application Server Setup](#3-application-server-setup)
4. [Install the MCP Server](#4-install-the-mcp-server)
5. [Environment Configuration](#5-environment-configuration)
6. [systemd Service](#6-systemd-service)
7. [NGINX Reverse Proxy with TLS](#7-nginx-reverse-proxy-with-tls)
8. [Observability Stack](#8-observability-stack)
9. [Security Hardening Checklist](#9-security-hardening-checklist)
10. [Smoke Tests and Verification](#10-smoke-tests-and-verification)
11. [Claude and AI Client Integration](#11-claude-and-ai-client-integration)
12. [HTTP API Reference](#12-http-api-reference)
13. [Operational Runbook](#13-operational-runbook)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

### Servers

| Role | Minimum Spec | Notes |
|------|-------------|-------|
| PostgreSQL server | 4 vCPU / 8 GB RAM | Dedicated instance; HA/backup assumed in place |
| Application server | 2 vCPU / 4 GB RAM | Runs MCP server + NGINX |
| Observability server | 2 vCPU / 8 GB RAM | OTel Collector, Tempo, Prometheus, Loki, Grafana |

### Supported OS

All steps are provided for three distributions. Run the block matching your OS.

```
Ubuntu 22.04 / Debian 12  →  use apt commands
RHEL 9 / Rocky Linux 9    →  use dnf commands
Amazon Linux 2023         →  use dnf commands (AL2023 variant)
```

### Ports

| Port | Service | Direction |
|------|---------|-----------|
| 443 | NGINX / MCP HTTPS | inbound from AI clients |
| 8000 | MCP HTTP (internal) | loopback only |
| 5432 | PostgreSQL | app server → DB server |
| 4317/4318 | OTel Collector gRPC/HTTP | app server → obs server |
| 9090 | Prometheus | obs server |
| 3100 | Loki | obs server |
| 3000 | Grafana | obs server |
| 14317 | Tempo gRPC | obs server (internal) |

---

## 2. PostgreSQL Server Setup

> Run these steps as a PostgreSQL superuser on the **database server**.

### 2.1 Create dedicated roles

```sql
-- Read-only role for exploratory / SELECT queries
CREATE ROLE mcp_read WITH LOGIN PASSWORD 'CHANGE_ME_read_strong_pass';

-- Write role for INSERT/UPDATE/DELETE (enable only if your use case requires it)
CREATE ROLE mcp_write WITH LOGIN PASSWORD 'CHANGE_ME_write_strong_pass';
```

### 2.2 Grant permissions

```sql
-- Connect to the target database
\c your_database

-- Read role: CONNECT + USAGE + SELECT on all existing + future objects
GRANT CONNECT ON DATABASE your_database TO mcp_read;
GRANT USAGE ON SCHEMA public TO mcp_read;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_read;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO mcp_read;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_read;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO mcp_read;

-- Explicitly deny write and DDL operations
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM mcp_read;
REVOKE CREATE ON SCHEMA public FROM mcp_read;

-- Write role: DML only on tables where AI writes are permitted
GRANT CONNECT ON DATABASE your_database TO mcp_write;
GRANT USAGE ON SCHEMA public TO mcp_write;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mcp_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mcp_write;
REVOKE CREATE ON SCHEMA public FROM mcp_write;
```

### 2.3 pg_hba.conf — restrict logins to app server IP

```
# /etc/postgresql/16/main/pg_hba.conf  (adjust path and version)
# TYPE  DATABASE        USER        ADDRESS           METHOD
hostssl your_database   mcp_read    10.0.1.20/32      scram-sha-256
hostssl your_database   mcp_write   10.0.1.20/32      scram-sha-256
```

Replace `10.0.1.20` with your application server's IP. Use `hostssl` to enforce TLS on all PostgreSQL connections.

### 2.4 postgresql.conf — tune for direct connections from the MCP server pool

```ini
# /etc/postgresql/16/main/postgresql.conf
max_connections = 100          # MCP server pool uses DB_POOL_MAX_SIZE per role
shared_buffers = 2GB           # 25% of RAM
work_mem = 16MB
maintenance_work_mem = 256MB
log_min_duration_statement = 1000   # log slow queries >= 1 s
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

Reload:
```bash
sudo systemctl reload postgresql
```

### 2.5 Enable pg_stat_statements

The `slow_queries` MCP tool reads from `pg_stat_statements`. Without it the tool returns an error.

```ini
# postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
pg_stat_statements.max = 10000
```

After editing `postgresql.conf`, restart PostgreSQL (a reload is not enough for `shared_preload_libraries`):

```bash
sudo systemctl restart postgresql
```

Then create the extension in your target database:

```sql
\c your_database
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Verify
SELECT count(*) FROM pg_stat_statements LIMIT 1;
```

Grant read access to the MCP read role:
```sql
GRANT SELECT ON pg_stat_statements TO mcp_read;
```

---

## 3. Application Server Setup

### 3.1 System packages

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip \
    nginx git curl jq

# RHEL / Rocky
sudo dnf install -y python3.12 python3.12-pip nginx git curl jq

# Amazon Linux 2023
sudo dnf install -y python3.12 python3.12-pip nginx git curl jq
```

### 3.2 Create a dedicated system user

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin mcpserver
sudo mkdir -p /opt/postgres-mcp-server
sudo mkdir -p /var/log/postgres-mcp
sudo chown mcpserver:mcpserver /opt/postgres-mcp-server /var/log/postgres-mcp
```

---

## 4. Install the MCP Server

### 4.1 Clone and create virtualenv

```bash
sudo -u mcpserver bash -c "
  git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server \
      /opt/postgres-mcp-server/app
  python3.12 -m venv /opt/postgres-mcp-server/venv
  /opt/postgres-mcp-server/venv/bin/pip install --upgrade pip
  /opt/postgres-mcp-server/venv/bin/pip install -r \
      /opt/postgres-mcp-server/app/requirements.txt
"
```

### 4.2 Verify installation

```bash
cd /opt/postgres-mcp-server/app
sudo -u mcpserver \
  /opt/postgres-mcp-server/venv/bin/python -c \
  "from mcp_server.http_app import create_app; print('OK')"
```

---

## 5. Environment Configuration

### 5.1 Create /opt/postgres-mcp-server/app/.env

```bash
sudo -u mcpserver tee /opt/postgres-mcp-server/app/.env > /dev/null << 'EOF'
# ── Transport ──────────────────────────────────────────────────────────────────
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8000

# ── Database DSNs (direct connection to PostgreSQL) ───────────────────────────
# Format: postgresql://user:pass@host:port/dbname
REMOTE_READ_DATABASE_URL=postgresql://mcp_read:CHANGE_ME@10.0.2.10:5432/your_database
REMOTE_WRITE_DATABASE_URL=postgresql://mcp_write:CHANGE_ME@10.0.2.10:5432/your_database

# Set DEFAULT_DB=remote for HTTP mode
DEFAULT_DB=remote

# ── Connection pool (asyncpg, per role) ───────────────────────────────────────
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=20
DB_CONNECT_TIMEOUT_SECONDS=5

# ── Query limits ─────────────────────────────────────────────────────────────
MAX_RESULT_ROWS=2000          # hard cap on rows returned per query
ALLOW_ARBITRARY_SQL=false     # keep false; only sql_safe is available

# ── Auth ─────────────────────────────────────────────────────────────────────
# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
MCP_HTTP_API_KEY=CHANGE_ME_replace_with_secure_random_key

# ── Audit log ────────────────────────────────────────────────────────────────
AUDIT_LOG_PATH=/var/log/postgres-mcp/mcp_audit.log
AUDIT_LOG_MAX_QUERY_PREVIEW=240

# ── OpenTelemetry ─────────────────────────────────────────────────────────────
OTEL_ENABLED=true
OTEL_SERVICE_NAME=postgres-mcp-server
OTEL_SERVICE_VERSION=1.0.0
OTEL_ENVIRONMENT=production
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://10.0.3.10:4318/v1/traces
EOF
```

Replace `10.0.2.10` with your PostgreSQL server IP and `10.0.3.10` with your observability server IP.

### 5.2 Lock down the env file

```bash
sudo chmod 600 /opt/postgres-mcp-server/app/.env
sudo chown mcpserver:mcpserver /opt/postgres-mcp-server/app/.env
```

### 5.3 Generate the API key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and replace CHANGE_ME_replace_with_secure_random_key in .env
```

---

## 6. systemd Service

### 6.1 Create the unit file

```bash
sudo tee /etc/systemd/system/postgres-mcp.service > /dev/null << 'EOF'
[Unit]
Description=PostgreSQL MCP Server (HTTP)
After=network.target

[Service]
Type=simple
User=mcpserver
Group=mcpserver
WorkingDirectory=/opt/postgres-mcp-server/app
EnvironmentFile=/opt/postgres-mcp-server/app/.env
ExecStart=/opt/postgres-mcp-server/venv/bin/python -m uvicorn \
    mcp_server.http_app:app \
    --host ${MCP_SERVER_HOST} \
    --port ${MCP_SERVER_PORT} \
    --workers 2 \
    --log-level info

Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=60s
StartLimitBurst=3

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/log/postgres-mcp
ProtectHome=true
CapabilityBoundingSet=

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=postgres-mcp

[Install]
WantedBy=multi-user.target
EOF
```

### 6.2 Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable postgres-mcp
sudo systemctl start postgres-mcp
sudo systemctl status postgres-mcp
```

### 6.3 Check it's listening

```bash
curl -s http://127.0.0.1:8000/healthz
# Expected: {"status":"ok", ...}

curl -s http://127.0.0.1:8000/readyz
# Expected: {"status":"ok", "pools": {...}}
```

---

## 7. NGINX Reverse Proxy with TLS

### 7.1 TLS certificate

**Option A — Let's Encrypt (Certbot)**
```bash
# Ubuntu / Debian
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d mcp.example.com

# RHEL / Rocky / Amazon Linux
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d mcp.example.com
```

**Option B — Existing PKI / commercial cert**
```bash
sudo mkdir -p /etc/nginx/tls
sudo cp fullchain.pem  /etc/nginx/tls/fullchain.pem
sudo cp privkey.pem    /etc/nginx/tls/privkey.pem
sudo chmod 600 /etc/nginx/tls/privkey.pem
sudo chown root:root /etc/nginx/tls/
```

### 7.2 NGINX configuration

Copy the production config from the repo:
```bash
sudo cp /opt/postgres-mcp-server/app/deployment/nginx/mcp-http.conf \
        /etc/nginx/conf.d/postgres-mcp.conf
```

Edit `/etc/nginx/conf.d/postgres-mcp.conf` and set your domain:
```nginx
server_name mcp.example.com;   # ← replace with your FQDN
```

The config includes:
- TLS 1.2/1.3 only with strong cipher suites
- HSTS (`Strict-Transport-Security: max-age=63072000`)
- Rate limiting: 10 req/s per IP, burst 20
- `X-Request-Id` propagation
- HTTP keepalive to upstream (`Connection ""` header)
- `client_max_body_size 256k`

### 7.3 Validate and reload NGINX

```bash
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx
```

### 7.4 Test HTTPS end-to-end

```bash
curl -s -H "x-api-key: YOUR_API_KEY" \
     https://mcp.example.com/healthz
# Expected: {"status":"ok", ...}
```

---

## 8. Observability Stack

> Run these steps on the **observability server**. Docker Compose is the simplest deployment.

### 8.1 Install Docker

```bash
# Ubuntu / Debian
sudo apt-get install -y docker.io docker-compose-plugin

# RHEL / Rocky / Amazon Linux 2023
sudo dnf install -y docker docker-compose-plugin
sudo systemctl enable --now docker
```

### 8.2 Copy observability configs

```bash
# Copy deployment configs to the observability server
scp -r /opt/postgres-mcp-server/app/deployment/otel \
        obs-server:/opt/observability/
```

### 8.3 docker-compose.yaml on the observability server

```yaml
# /opt/observability/docker-compose.yaml
version: "3.9"

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.96.0
    volumes:
      - ./otel/otel-collector.yaml:/etc/otel-collector.yaml:ro
    command: ["--config=/etc/otel-collector.yaml"]
    ports:
      - "4317:4317"    # gRPC ingest
      - "4318:4318"    # HTTP ingest
      - "9464:9464"    # Prometheus scrape endpoint
    restart: unless-stopped

  tempo:
    image: grafana/tempo:2.4.1
    volumes:
      - ./tempo/tempo.yaml:/etc/tempo.yaml:ro
      - tempo-data:/var/tempo
    command: ["-config.file=/etc/tempo.yaml"]
    ports:
      - "14317:14317"  # OTel gRPC ingestion from collector
      - "3200:3200"    # Tempo query API
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:v2.51.2
    volumes:
      - ./prometheus/prometheus.yaml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  loki:
    image: grafana/loki:2.9.7
    volumes:
      - ./loki/loki.yaml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki
    ports:
      - "3100:3100"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.4.2
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    environment:
      GF_SECURITY_ADMIN_PASSWORD: "CHANGE_ME_grafana_admin_pass"
      GF_PATHS_PROVISIONING: /etc/grafana/provisioning
    ports:
      - "3000:3000"
    restart: unless-stopped

volumes:
  tempo-data:
  prometheus-data:
  loki-data:
  grafana-data:
```

### 8.4 Prometheus scrape config

```yaml
# /opt/observability/prometheus/prometheus.yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: postgres-mcp-server
    static_configs:
      - targets: ["10.0.3.10:9464"]   # OTel Collector Prometheus endpoint
        labels:
          app: postgres-mcp-server
          env: production
```

### 8.5 Tempo config

```yaml
# /opt/observability/tempo/tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:14317"

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/blocks
    wal:
      path: /var/tempo/wal

compactor:
  compaction:
    block_retention: 336h  # 14 days
```

### 8.6 Loki config

```yaml
# /opt/observability/loki/loki.yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  tsdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  allow_structured_metadata: true   # required for trace_id/span_id correlation
  retention_period: 336h            # 14 days
```

### 8.7 Promtail on the application server

```bash
# Ubuntu / Debian
sudo apt-get install -y promtail

# RHEL / Rocky / Amazon Linux — install from binary
curl -sLO https://github.com/grafana/loki/releases/download/v2.9.7/promtail-linux-amd64.zip
unzip promtail-linux-amd64.zip
sudo install -m 755 promtail-linux-amd64 /usr/local/bin/promtail
```

Copy the Promtail config:
```bash
sudo cp /opt/postgres-mcp-server/app/deployment/promtail/promtail.local.yaml \
        /etc/promtail/promtail.yaml
```

Edit `/etc/promtail/promtail.yaml` for production — update the Loki URL and log path:
```yaml
clients:
  - url: http://10.0.3.10:3100/loki/api/v1/push   # observability server

scrape_configs:
  - job_name: postgres-mcp-audit
    static_configs:
      - targets:
          - localhost
        labels:
          job: postgres-mcp-audit
          app: postgres-mcp-server
          env: production
          __path__: /var/log/postgres-mcp/mcp_audit.log
    pipeline_stages:
      - json:
          expressions:
            timestamp: timestamp
            level: level
            tool_name: tool_name
            transport: transport
            ok: ok
            request_id: request_id
            trace_id: trace_id
            span_id: span_id
      - labels:
          level:
          tool_name:
          transport:
          ok:
      - structured_metadata:
          trace_id: trace_id
          span_id: span_id
      - timestamp:
          source: timestamp
          format: RFC3339Nano
```

Start Promtail:
```bash
sudo systemctl enable promtail
sudo systemctl start promtail
```

### 8.8 Start the observability stack

```bash
cd /opt/observability
docker compose up -d
docker compose ps
```

### 8.9 Grafana data sources

Log into Grafana at `http://obs-server:3000` (admin / your password) and add:

| Name | Type | URL |
|------|------|-----|
| Prometheus | Prometheus | `http://prometheus:9090` |
| Tempo | Tempo | `http://tempo:3200` |
| Loki | Loki | `http://loki:3100` |

In the Loki data source, configure **Derived fields** for log → trace click-through:
- Name: `TraceID`
- Regex: `"trace_id":"([a-f0-9]{32})"`
- URL: linked to the Tempo data source, value: `${__value.raw}`

### 8.10 Import the starter Grafana dashboard

The repo ships a pre-built overview dashboard at `deployment/grafana/postgres-mcp-local-overview.json`. It covers:
- Tempo ingestion health
- Audit event rates by level and tool name (from Loki)
- Recent audit failures and recent events

**Import steps:**
1. Confirm the Prometheus, Loki, and Tempo data sources are saved in Grafana.
2. Open **Dashboards → New → Import** in the Grafana UI.
3. Upload `deployment/grafana/postgres-mcp-local-overview.json`.
4. Map the prompted variables:
   - `DS_PROMETHEUS` → your Prometheus data source
   - `DS_LOKI` → your Loki data source
5. Click **Import**.

For richer trace exploration, open **Explore → Tempo** and run:
```
{ resource.service.name = "postgres-mcp-server" }
```

---

## 9. Security Hardening Checklist

### PostgreSQL
- [ ] `mcp_read` and `mcp_write` roles have no SUPERUSER, CREATEDB, or CREATEROLE attributes
- [ ] `pg_hba.conf` restricts logins to the application server IP only with `hostssl`
- [ ] `mcp_read` cannot write: `REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM mcp_read`
- [ ] `REVOKE CREATE ON SCHEMA public FROM mcp_read, mcp_write`
- [ ] `ALLOW_ARBITRARY_SQL=false` in production `.env`
- [ ] Password rotation schedule defined (see §11.4)

### Application server
- [ ] `mcpserver` system user has no shell (`/usr/sbin/nologin`) and no home directory
- [ ] `.env` is `chmod 600`, owned by `mcpserver`
- [ ] `MCP_HTTP_API_KEY` is a 64-character random hex value
- [ ] systemd unit has `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectHome=true`
- [ ] Port 8000 is loopback-only; NGINX is the only public entry point

```bash
# Ubuntu / Debian (ufw)
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw enable

# RHEL / Rocky / Amazon Linux (firewalld)
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-rich-rule='rule port port="8000" protocol="tcp" reject'
sudo firewall-cmd --reload
```

### NGINX
- [ ] TLS 1.2 / 1.3 only; no SSLv3/TLSv1/TLSv1.1
- [ ] HSTS with `max-age=63072000`
- [ ] Rate limiting active: 10 req/s per IP, burst 20
- [ ] `client_max_body_size 256k`
- [ ] Access and error logs enabled and rotated

### Audit trail
- [ ] Audit log directory writable by `mcpserver` only
- [ ] Log rotation configured (§11.5)
- [ ] Audit logs shipped to Loki for long-term retention

---

## 10. Smoke Tests and Verification

### 10.1 Health and readiness

```bash
# Via NGINX (public endpoint)
curl -sf https://mcp.example.com/healthz | jq .
curl -sf https://mcp.example.com/readyz | jq .
```

Expected `readyz` output:
```json
{
  "status": "ok",
  "pools": {
    "remote_read": {"initialized": true, "min_size": 2, "max_size": 20, ...},
    "remote_write": {"initialized": true, ...}
  }
}
```

### 10.2 Authenticated tool call

```bash
API_KEY="your_key_here"
curl -sf -X POST https://mcp.example.com/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "jsonrpc":"2.0","id":1,"method":"tools/call",
    "params":{"name":"get_schema","arguments":{}}
  }' | jq .
```

### 10.3 Read-only enforcement

```bash
curl -sf -X POST https://mcp.example.com/mcp \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "jsonrpc":"2.0","id":2,"method":"tools/call",
    "params":{"name":"run_query","arguments":{"query":"DROP TABLE users","db":"remote_read"}}
  }' | jq .result.error
# Expected: "cannot execute DROP TABLE in a read-only transaction"
```

### 10.4 Rate limit

```bash
for i in $(seq 1 30); do
  curl -so /dev/null -w "%{http_code}\n" \
    -H "x-api-key: $API_KEY" https://mcp.example.com/healthz
done
# Requests 21–30 should return 503 (rate limited by NGINX)
```

### 10.5 Verify audit logging

```bash
sudo tail -20 /var/log/postgres-mcp/mcp_audit.log | python3 -m json.tool | head -60
```

Each line should be valid JSON with fields: `timestamp`, `tool_name`, `ok`, `request_id`, `trace_id`, `span_id`, `query_hash`, `query_preview`.

### 10.6 Verify trace flow

After a tool call, check Grafana → Tempo for a trace named `mcp.tool_call`. In Loki, run:
```logql
{app="postgres-mcp-server"} | json | trace_id != ""
```
Click the trace ID link — it should navigate to the matching Tempo trace.

---

## 11. Claude and AI Client Integration

This server supports two integration modes depending on where Claude is running.

### 11.1 Transport overview

| Mode | Transport | When to use |
|------|-----------|-------------|
| STDIO | Process launch via launcher script | Claude Desktop on a developer's Mac; no server needed |
| HTTP REST | `https://mcp.example.com/...` | Production; Claude Code, remote AI clients, automation |

### 11.2 Claude Desktop — STDIO (developer / local)

Claude Desktop launches `cli.py` as a subprocess over STDIO. Credentials never appear in `claude_desktop_config.json`.

**Step 1 — Create env files on the developer's machine**

```bash
# Clone the repo locally
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server
cd postgres-mcp-server
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# Local database target
cp .env.example .env.claude.local
# Edit .env.claude.local:
#   DEFAULT_DB=local
#   LOCAL_READ_DATABASE_URL=postgresql://mcp_read:PASSWORD@localhost:5432/your_database
#   LOCAL_WRITE_DATABASE_URL=postgresql://mcp_write:PASSWORD@localhost:5432/your_database

# Remote / production database target
cp .env.example .env.claude.remote
# Edit .env.claude.remote:
#   DEFAULT_DB=remote
#   REMOTE_READ_DATABASE_URL=postgresql://mcp_read:PASSWORD@10.0.2.10:5432/your_database
#   REMOTE_WRITE_DATABASE_URL=postgresql://mcp_write:PASSWORD@10.0.2.10:5432/your_database
```

Both files are git-ignored by default (`.env.*` pattern in `.gitignore`).

**Step 2 — Add to Claude Desktop config**

Config file location:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

Replace `/Users/yourname/postgres-mcp-server` with the actual clone path.

**Step 3 — Restart Claude Desktop**

After saving the config, quit and reopen Claude Desktop. The tool list in the sidebar should show the MCP server tools (health, schema, sql_safe, etc.).

### 11.3 Claude Code CLI — HTTP (production)

Claude Code can call the production HTTP server directly using a project-level MCP config.

Create `.mcp.json` in your project root (or `~/.claude/mcp.json` for a user-global config):

```json
{
  "mcpServers": {
    "postgres-mcp": {
      "type": "http",
      "url": "https://mcp.example.com",
      "headers": {
        "x-api-key": "YOUR_MCP_HTTP_API_KEY"
      }
    }
  }
}
```

Or pass it on the command line for a one-off session:

```bash
claude --mcp-server "postgres-mcp=https://mcp.example.com" \
       --header "x-api-key=YOUR_KEY" \
       "Show me the schema and top 5 largest tables"
```

### 11.4 Other AI clients — HTTP

Any AI agent or automation that can call REST endpoints can use the HTTP server. Pass the API key in the `x-api-key` header. Example with curl:

```bash
API_KEY="your_key"
BASE="https://mcp.example.com"

# Schema
curl -sf -H "x-api-key: $API_KEY" "$BASE/get_schema" | jq .

# Read-only query
curl -sf -X POST -H "x-api-key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query": "SELECT count(*) FROM orders WHERE created_at > now() - interval 7 day"}' \
     "$BASE/sql_safe_query" | jq .
```

---

## 12. HTTP API Reference

All endpoints require the `x-api-key` header when `MCP_HTTP_API_KEY` is set.

### Diagnostic

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` or `/healthz` | Liveness check — PostgreSQL version + current user |
| GET | `/readyz` | Readiness — pool status for all configured roles |
| GET | `/uptime` | Postmaster start time and uptime |
| GET | `/config_status` | Safe runtime config summary (no secrets) |
| GET | `/pool_status` | Connection pool utilisation per role |

### Schema and metadata

| Method | Path | Description |
|--------|------|-------------|
| GET | `/get_schema` | Public schema: tables, columns, types |
| GET | `/stats/table_stats?limit=N` | Table sizes and row estimates |
| GET | `/stats/slow_queries?limit=N` | Top queries from `pg_stat_statements` |
| GET | `/index_usage?limit=N` | Index scan counts, sizes, and unused indexes |
| GET | `/locks?limit=N` | Blocked sessions and blockers |
| GET | `/vacuum_status?limit=N` | Vacuum/analyze state and dead tuple pressure |
| GET | `/replication_status?limit=N` | Replica, slot, and recovery status |
| GET | `/access_scope?limit=N` | Schemas and tables visible to the read role |

### Query execution

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/sql_safe_query` | `{"query": "SELECT ..."}` | Single read-only statement in a read-only transaction |
| POST | `/sql_query` | `{"query": "..."}` | Arbitrary SQL — only works when `ALLOW_ARBITRARY_SQL=true` |
| POST | `/explain_query` | `{"query": "...", "analyze": false}` | JSON EXPLAIN plan |
| POST | `/index_advisor` | `{"query": "SELECT ..."}` | Index recommendations from the query plan |
| POST | `/redaction_test` | `{"value": "..."}` | Preview PII masking on a sample value |

### Audit

| Method | Path | Query params | Description |
|--------|------|-------------|-------------|
| GET | `/audit_logs` | `limit`, `tool_name`, `ok` | Recent structured audit events with optional filters |
| GET | `/audit_summary` | `limit` | Aggregated activity, failure counts, common errors |

---

## 13. Operational Runbook

### 11.1 Start / stop / restart

```bash
sudo systemctl start   postgres-mcp
sudo systemctl stop    postgres-mcp
sudo systemctl restart postgres-mcp
sudo systemctl status  postgres-mcp
```

### 11.2 Rolling upgrade (zero-downtime)

```bash
# 1. Pull new code
sudo -u mcpserver git -C /opt/postgres-mcp-server/app pull

# 2. Install any new dependencies
sudo -u mcpserver /opt/postgres-mcp-server/venv/bin/pip install -r \
    /opt/postgres-mcp-server/app/requirements.txt

# 3. Restart (uvicorn handles SIGTERM gracefully — drains in-flight requests)
sudo systemctl restart postgres-mcp

# 4. Confirm healthy
curl -sf http://127.0.0.1:8000/readyz | jq .status
```

### 11.3 Check application logs

```bash
# Realtime
sudo journalctl -u postgres-mcp -f

# Last 100 lines
sudo journalctl -u postgres-mcp -n 100 --no-pager

# Filter errors only
sudo journalctl -u postgres-mcp -p err --since "1 hour ago"
```

### 11.4 Credential rotation

**Rotate PostgreSQL password:**
```sql
-- On the DB server
ALTER ROLE mcp_read  WITH PASSWORD 'NEW_STRONG_PASSWORD_read';
ALTER ROLE mcp_write WITH PASSWORD 'NEW_STRONG_PASSWORD_write';
```

**Update .env and restart:**
```bash
sudo -u mcpserver nano /opt/postgres-mcp-server/app/.env
# Update REMOTE_READ_DATABASE_URL and REMOTE_WRITE_DATABASE_URL

sudo systemctl restart postgres-mcp
curl -sf http://127.0.0.1:8000/readyz | jq .
```

**Rotate the MCP API key:**
```bash
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "New key: $NEW_KEY"

# Update .env
sudo -u mcpserver sed -i \
  "s|^MCP_HTTP_API_KEY=.*|MCP_HTTP_API_KEY=$NEW_KEY|" \
  /opt/postgres-mcp-server/app/.env

sudo systemctl restart postgres-mcp

# Update the key in all AI client configurations (Claude Desktop, etc.)
```

### 11.5 Log rotation

```bash
sudo tee /etc/logrotate.d/postgres-mcp << 'EOF'
/var/log/postgres-mcp/mcp_audit.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 mcpserver mcpserver
    postrotate
        systemctl kill -s HUP postgres-mcp > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 11.6 Connection pool monitoring

```bash
# Check pool stats via the readyz endpoint
curl -sf http://127.0.0.1:8000/readyz | jq .pools
```

Look for `in_use` values climbing toward `max_size` (20 by default). If `in_use` is consistently at `max_size`, increase `DB_POOL_MAX_SIZE` in `.env` and also raise `max_connections` in `postgresql.conf` accordingly.

---

## 12. Troubleshooting

### MCP server won't start

```bash
sudo journalctl -u postgres-mcp -n 50 --no-pager
```

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `asyncpg.InvalidPasswordError` | Wrong DB password in `.env` | Verify credentials; `ALTER ROLE mcp_read WITH PASSWORD` |
| `ConnectionRefusedError port 5432` | PostgreSQL unreachable | Check firewall, `pg_hba.conf`, and that PostgreSQL is running |
| `Address already in use :8000` | Port conflict | `sudo ss -tlnp \| grep 8000`; stop conflicting service |
| `EnvironmentFile not found` | `.env` path wrong in unit | Verify `EnvironmentFile=` in the systemd unit file |
| `permission denied /var/log/postgres-mcp` | Wrong ownership | `sudo chown mcpserver:mcpserver /var/log/postgres-mcp` |
| `asyncpg.TooManyConnectionsError` | DB `max_connections` too low | Raise `max_connections` in `postgresql.conf` |

### NGINX returns 502 Bad Gateway

```bash
sudo nginx -t                           # config syntax
sudo journalctl -u nginx -n 20          # nginx errors
curl -sf http://127.0.0.1:8000/healthz  # MCP server directly
```

If the direct call works, the issue is the NGINX → upstream config (check `proxy_pass` address and port).

### 401 Unauthorized from API

```bash
# Verify key in .env
sudo grep MCP_HTTP_API_KEY /opt/postgres-mcp-server/app/.env

# Test directly with the key
curl -sf -H "x-api-key: $(sudo grep MCP_HTTP_API_KEY \
     /opt/postgres-mcp-server/app/.env | cut -d= -f2)" \
     http://127.0.0.1:8000/healthz
```

If this works but the NGINX path returns 401, check that NGINX is forwarding the `x-api-key` header (`proxy_set_header` lines in `mcp-http.conf`).

### Queries fail or return wrong database

```bash
# Confirm DEFAULT_DB is remote
sudo grep DEFAULT_DB /opt/postgres-mcp-server/app/.env

# Check pool is initialized for remote_read / remote_write
curl -sf http://127.0.0.1:8000/readyz | jq .pools
```

### Traces not appearing in Tempo

```bash
# Confirm OTEL is enabled
sudo grep OTEL_ENABLED /opt/postgres-mcp-server/app/.env

# Test OTel Collector HTTP endpoint reachability
curl -sf -X POST http://10.0.3.10:4318/v1/traces \
  -H "Content-Type: application/json" -d '{}' -o /dev/null -w "%{http_code}"
# Expected: 200

# Check OTel Collector logs on the obs server
docker compose -f /opt/observability/docker-compose.yaml logs otel-collector | tail -20
```

### Audit logs not in Loki

```bash
# Check Promtail is running
sudo systemctl status promtail

# Check Promtail can read the audit log
sudo -u mcpserver test -r /var/log/postgres-mcp/mcp_audit.log && echo readable

# Check Loki endpoint reachability
curl -sf http://10.0.3.10:3100/ready

# Check Promtail logs for push errors
sudo journalctl -u promtail -n 50 --no-pager
```

---

*Review this guide against the configs in [deployment/](deployment/) before each deployment.*
