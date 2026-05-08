# Local Integration Test

Use this sequence to validate the local observability path on macOS with Docker Desktop. This is a local validation flow, not a production deployment recipe.

## 1. Prerequisites

- Docker Desktop is running
- Grafana is available at `http://127.0.0.1:3000`
- `otelcol-contrib` is installed locally
- repo dependencies are installed in `venv`

## 2. Start the local backends

Start Tempo:

```bash
./scripts/start_tempo_local.sh
```

In a new terminal, wait for readiness:

```bash
curl http://127.0.0.1:3200/ready
```

Expected:

```text
ready
```

Start the OpenTelemetry Collector:

```bash
./scripts/start_otel_collector_local.sh
```

Optional metrics and log backends:

```bash
./scripts/start_prometheus_local.sh
./scripts/start_loki_local.sh
./scripts/start_promtail_local.sh
```

## 3. Start the HTTP app with tracing enabled

```bash
./scripts/start_mcp_http_otel_local.sh
```

Expected startup log:

```text
OpenTelemetry tracing enabled
```

## 4. Generate traffic

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

If your HTTP API key is enabled, include `-H "x-api-key: <value>"` on protected routes.

To create a DB-backed trace and audit event:

```bash
curl -H "x-api-key: change-me" http://127.0.0.1:8000/
curl "http://127.0.0.1:8000/audit_logs?limit=5" -H "x-api-key: change-me"
```

## 5. Verify Tempo ingestion

```bash
curl -s http://127.0.0.1:3200/metrics | grep tempo_distributor_traces_per_batch_count
```

Expected:

```text
tempo_distributor_traces_per_batch_count 1
```

Any value greater than `0` confirms Collector -> Tempo export is working.

## 6. Verify Grafana traces

Add a Tempo datasource in Grafana with URL:

```text
http://127.0.0.1:3200
```

In Grafana Explore, use TraceQL:

```traceql
{}
```

Then narrow to this service:

```traceql
{ resource.service.name = "postgres-mcp-server" }
```

Set the time range to `Last 15 minutes` or `Last 1 hour`.

## 7. Verify request correlation

Check the response header:

```bash
curl -i http://127.0.0.1:8000/healthz
```

Expected header:

```text
X-Request-Id: <generated-id>
```

Check the latest audit event:

```bash
tail -n 1 mcp_audit.log
```

Expected fields:

- `request_id`
- `trace_id`
- `span_id`

Those values let you correlate an HTTP request, the audit JSONL record, and the trace in Grafana.

## 8. Verify Claude Desktop STDIO tracing

Add this to `.env.claude.local` if it is not already present:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=postgres-mcp-server
OTEL_ENVIRONMENT=local
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

Restart Claude Desktop, then run a few MCP-backed prompts.

Expected result:

- new traces appear in Tempo for service `postgres-mcp-server`
- audit events from transport `mcp` include `request_id`, `trace_id`, and `span_id`

## 9. Optional local NGINX proxy test

If you want to test the HTTP MCP path through NGINX locally:

1. Start the HTTP app:

```bash
./scripts/start_mcp_http_otel_local.sh
```

2. Start local NGINX:

```bash
./scripts/start_nginx_local.sh
```

3. Test the proxy:

```bash
curl http://127.0.0.1:8081/healthz
curl -H "x-api-key: change-me" http://127.0.0.1:8081/
```

Expected:

- the requests succeed through NGINX
- the response includes `X-Request-Id`
- the HTTP spans still appear in Tempo

The local starter script uses Docker-based NGINX so it does not depend on a working host `nginx` binary.
