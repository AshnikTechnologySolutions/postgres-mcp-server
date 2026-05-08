# Observability Starter

This folder contains starter configuration for placing an HTTP-exposed MCP service behind NGINX and routing telemetry through OpenTelemetry Collector, Tempo, Prometheus, and Loki.

## Recommended topology

- Remote AI client -> NGINX -> FastAPI MCP service -> PostgreSQL
- MCP service -> OTLP -> OpenTelemetry Collector
- NGINX logs -> file shipper or collector sidecar
- Collector -> Grafana stack or other backends

## Components

- `../nginx/mcp-http.conf`: reverse proxy starter config
- `../otel/otel-collector.yaml`: general collector starter config
- `../otel/otel-collector.local.yaml`: local macOS collector config
- `../otel/tempo.local.yaml`: local Tempo config for containerized startup
- `../prometheus/prometheus.local.yaml`: local Prometheus scrape config
- `../loki/loki.local.yaml`: local Loki config
- `../promtail/promtail.local.yaml`: local Promtail config for audit log shipping
- `../nginx/mcp-http.local.conf`: local non-TLS host-NGINX config for testing
- `../nginx/mcp-http.local.docker.conf`: local non-TLS Docker-NGINX config for testing
- `../grafana/postgres-mcp-local-overview.json`: starter Grafana overview dashboard
- `./LOCAL_INTEGRATION_TEST.md`: exact local validation sequence

## Notes

- Do not use NGINX for local Claude Desktop STDIO mode.
- Use NGINX only when you expose the HTTP adapter remotely.
- Keep `MCP_HTTP_API_KEY` enabled for HTTP deployments.
- The current repo includes the HTTP app entrypoint at `mcp_server/http_app.py`.
- Files ending in `.local.*` are local validation starters, not production deployment configs.
- The local Docker Desktop flow assumes macOS-style `host.docker.internal` routing unless you override the relevant environment values.

## Start the HTTP app

```bash
uvicorn mcp_server.http_app:app --host 127.0.0.1 --port 8000
```

## Local Mac sequence

If you want a local trace backend on macOS:

1. Start Tempo in Docker Desktop:

```bash
./scripts/start_tempo_local.sh
```

2. Wait for Tempo:

```bash
curl http://127.0.0.1:3200/ready
```

3. Start OTel Collector:

```bash
./scripts/start_otel_collector_local.sh
```

4. Start the MCP HTTP app with tracing enabled:

```bash
./scripts/start_mcp_http_otel_local.sh
```

5. Optional metrics and logs stack:

```bash
./scripts/start_prometheus_local.sh
./scripts/start_loki_local.sh
./scripts/start_promtail_local.sh
```

6. Generate test traffic:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

7. Confirm Tempo ingestion:

```bash
curl -s http://127.0.0.1:3200/metrics | grep tempo_distributor_traces_per_batch_count
```

Any value greater than `0` confirms the local trace pipeline is working.

## Production deployment note

For production or multi-machine deployment:

- run Tempo, Prometheus, Loki, and Grafana with environment-specific storage and hostnames
- point Tempo metrics-generator remote write at a real Prometheus endpoint instead of the local Docker Desktop default
- use TLS and auth at NGINX
- avoid local-only paths like `/tmp/tempo-*` unless they are intentionally ephemeral

## Correlation

The HTTP app adds an `X-Request-Id` response header and stamps the same request ID into:

- FastAPI spans as `http.request_id`
- audit JSONL records as `request_id`
- audit JSONL records as `trace_id` and `span_id`

## Tempo-style drilldowns

To get closer to the Grafana Tempo documentation experience, the local Tempo starter now enables:

- `service-graphs`
- `span-metrics`
- `local-blocks`

Those are produced by Tempo metrics-generator and remote-written into Prometheus. Prometheus must therefore run with the remote write receiver enabled, which is already handled by `scripts/start_prometheus_local.sh`.

After restarting Tempo and Prometheus, link your Tempo datasource to the Prometheus datasource in Grafana so the Service Graph and span-metric views have a metrics backend.

## Suggested dashboards

- MCP requests by endpoint
- MCP error rate
- request latency by endpoint
- database latency by tool
- slow query frequency
- audit log error volume
- NGINX upstream latency and 4xx/5xx rates
- Tempo ingestion rate
- Collector exporter failures
- Prometheus scrape health
