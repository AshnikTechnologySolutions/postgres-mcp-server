import os
import re
from collections import Counter

from mcp_server.audit import read_audit_events
from mcp_server.config import ALLOW_ARBITRARY_SQL, DB_POOL_MAX_SIZE, DB_POOL_MIN_SIZE, DEFAULT_DB
from mcp_server.db import describe_pools, get_pool
from mcp_server.sql import QueryValidationError, coerce_limit, detect_pg_stat_statements_columns, fetch_rows


async def readiness():
    checks = {
        "database": {"ok": False},
        "pg_stat_statements": {"ok": False},
    }

    try:
        rows = await fetch_rows(
            """
            SELECT
                current_database() AS database_name,
                current_user AS database_user,
                version() AS postgres_version
            """,
            role="read",
            read_only=True,
        )
        checks["database"] = {"ok": True, **rows[0]}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)}

    try:
        total_col, mean_col = await detect_pg_stat_statements_columns()
        checks["pg_stat_statements"] = {
            "ok": True,
            "timing_columns": [total_col, mean_col],
        }
    except Exception as exc:
        checks["pg_stat_statements"] = {"ok": False, "error": str(exc)}

    # Only database connectivity gates readiness. pg_stat_statements is optional
    # (only affects slow_queries); its absence must not 503 a load-balancer probe.
    db_ok = checks["database"]["ok"]
    all_ok = all(check["ok"] for check in checks.values())
    status = "ready" if all_ok else ("degraded" if db_ok else "unavailable")
    return {"ok": db_ok, "status": status, "checks": checks}


async def config_status():
    return {
        "ok": True,
        "config": {
            "default_db": DEFAULT_DB,
            "allow_arbitrary_sql": ALLOW_ARBITRARY_SQL,
            "db_pool_min_size": int(os.getenv("DB_POOL_MIN_SIZE", "2")),
            "db_pool_max_size": int(os.getenv("DB_POOL_MAX_SIZE", "20")),
            "db_connect_timeout_seconds": float(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
            "max_result_rows": int(os.getenv("MAX_RESULT_ROWS", "2000")),
            "audit_log_path": os.getenv("AUDIT_LOG_PATH", "mcp_audit.log"),
            "audit_log_max_query_preview": int(os.getenv("AUDIT_LOG_MAX_QUERY_PREVIEW", "240")),
            "mcp_http_api_key_enabled": bool(os.getenv("MCP_HTTP_API_KEY")),
            "otel_enabled": os.getenv("OTEL_ENABLED", "false").strip().lower() == "true",
            "otel_service_name": os.getenv("OTEL_SERVICE_NAME", "postgres-mcp-server"),
            "otel_environment": os.getenv("OTEL_ENVIRONMENT", "development"),
            "otel_exporter_otlp_traces_endpoint": os.getenv(
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:4318/v1/traces"
            ),
        },
    }


async def audit_summary(limit: int = 200):
    try:
        safe_limit = coerce_limit(limit, default=200)
        events = await read_audit_events(limit=safe_limit)
        by_tool = Counter()
        failures_by_tool = Counter()
        errors = Counter()

        for event in events:
            tool_name = event.get("tool_name", "unknown")
            by_tool[tool_name] += 1
            if not event.get("ok", False):
                failures_by_tool[tool_name] += 1
                if event.get("error"):
                    errors[str(event["error"])] += 1

        top_errors = [{"error": error, "count": count} for error, count in errors.most_common(10)]
        return {
            "ok": True,
            "summary": {
                "scanned_events": len(events),
                "calls_by_tool": dict(by_tool),
                "failures_by_tool": dict(failures_by_tool),
                "top_errors": top_errors,
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def access_scope(limit: int = 200):
    try:
        safe_limit = coerce_limit(limit, default=200)
        rows = await fetch_rows(
            f"""
            SELECT
                t.table_schema,
                t.table_name,
                CASE
                    WHEN has_table_privilege(
                        current_user,
                        quote_ident(t.table_schema) || '.' || quote_ident(t.table_name),
                        'SELECT'
                    )
                    THEN true
                    ELSE false
                END AS can_select
            FROM information_schema.tables t
            WHERE t.table_type IN ('BASE TABLE', 'VIEW')
              AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY t.table_schema, t.table_name
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        visible = [row for row in rows if row.get("can_select")]
        schemas = sorted({row["table_schema"] for row in visible})
        return {
            "ok": True,
            "scope": {
                "schema_count": len(schemas),
                "visible_object_count": len(visible),
                "schemas": schemas,
                "objects": visible,
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def pool_status():
    try:
        await get_pool(role="read")
        if ALLOW_ARBITRARY_SQL:
            await get_pool(role="write")
        return {
            "ok": True,
            "pools": describe_pools(),
            "configured": {
                "min_size": DB_POOL_MIN_SIZE,
                "max_size": DB_POOL_MAX_SIZE,
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def locks(limit: int = 50):
    try:
        safe_limit = coerce_limit(limit, default=50)
        rows = await fetch_rows(
            f"""
            WITH blocked AS (
                SELECT
                    a.pid AS blocked_pid,
                    a.usename AS blocked_user,
                    a.application_name AS blocked_application,
                    a.state AS blocked_state,
                    a.wait_event_type,
                    a.wait_event,
                    age(now(), a.query_start) AS blocked_duration,
                    left(a.query, 400) AS blocked_query,
                    unnest(pg_blocking_pids(a.pid)) AS blocking_pid
                FROM pg_stat_activity a
                WHERE a.datname = current_database()
                  AND cardinality(pg_blocking_pids(a.pid)) > 0
            )
            SELECT
                b.blocked_pid,
                b.blocked_user,
                b.blocked_application,
                b.blocked_state,
                b.wait_event_type,
                b.wait_event,
                b.blocked_duration,
                b.blocked_query,
                b.blocking_pid,
                blocker.usename AS blocking_user,
                blocker.application_name AS blocking_application,
                blocker.state AS blocking_state,
                age(now(), blocker.query_start) AS blocking_duration,
                left(blocker.query, 400) AS blocking_query
            FROM blocked b
            LEFT JOIN pg_stat_activity blocker ON blocker.pid = b.blocking_pid
            ORDER BY b.blocked_duration DESC, b.blocked_pid
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        return {
            "ok": True,
            "locks": rows,
            "summary": {
                "blocked_session_count": len(rows),
                "limit": safe_limit,
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def index_usage(limit: int = 100):
    try:
        safe_limit = coerce_limit(limit, default=100)
        rows = await fetch_rows(
            f"""
            SELECT
                s.schemaname,
                s.relname AS table_name,
                s.indexrelname AS index_name,
                s.idx_scan,
                s.idx_tup_read,
                s.idx_tup_fetch,
                pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
                i.indisunique AS is_unique,
                i.indisprimary AS is_primary,
                CASE
                    WHEN s.idx_scan = 0 THEN 'unused'
                    WHEN s.idx_scan < 50 THEN 'low'
                    ELSE 'active'
                END AS usage_state
            FROM pg_stat_user_indexes s
            JOIN pg_index i ON i.indexrelid = s.indexrelid
            ORDER BY s.idx_scan ASC, pg_relation_size(s.indexrelid) DESC
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        usage_counts = Counter(row["usage_state"] for row in rows)
        return {
            "ok": True,
            "indexes": rows,
            "summary": {
                "limit": safe_limit,
                "returned": len(rows),
                "usage_state_counts": dict(usage_counts),
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def vacuum_status(limit: int = 100):
    try:
        safe_limit = coerce_limit(limit, default=100)
        rows = await fetch_rows(
            f"""
            SELECT
                schemaname,
                relname AS table_name,
                n_live_tup,
                n_dead_tup,
                vacuum_count,
                autovacuum_count,
                analyze_count,
                autoanalyze_count,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                CASE
                    WHEN n_live_tup = 0 THEN 0
                    ELSE round((n_dead_tup::numeric / NULLIF(n_live_tup, 0)) * 100, 2)
                END AS dead_tuple_pct
            FROM pg_stat_user_tables
            ORDER BY n_dead_tup DESC, relname
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        return {
            "ok": True,
            "tables": rows,
            "summary": {
                "limit": safe_limit,
                "returned": len(rows),
                "tables_with_dead_tuples": sum(1 for row in rows if (row.get("n_dead_tup") or 0) > 0),
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def replication_status(limit: int = 50):
    try:
        safe_limit = coerce_limit(limit, default=50)
        recovery_rows = await fetch_rows(
            """
            SELECT
                pg_is_in_recovery() AS in_recovery,
                CASE
                    WHEN pg_is_in_recovery() THEN pg_last_wal_replay_lsn()::text
                    ELSE pg_current_wal_lsn()::text
                END AS current_lsn
            """,
            role="read",
            read_only=True,
        )
        replication_rows = await fetch_rows(
            f"""
            SELECT
                pid,
                application_name,
                client_addr::text AS client_addr,
                state,
                sync_state,
                write_lag,
                flush_lag,
                replay_lag,
                sent_lsn::text AS sent_lsn,
                write_lsn::text AS write_lsn,
                flush_lsn::text AS flush_lsn,
                replay_lsn::text AS replay_lsn
            FROM pg_stat_replication
            ORDER BY application_name, pid
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        slot_rows = await fetch_rows(
            f"""
            SELECT
                slot_name,
                slot_type,
                active,
                restart_lsn::text AS restart_lsn,
                confirmed_flush_lsn::text AS confirmed_flush_lsn,
                wal_status
            FROM pg_replication_slots
            ORDER BY slot_name
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        recovery = recovery_rows[0] if recovery_rows else {}
        return {
            "ok": True,
            "replication": {
                "instance": recovery,
                "replicas": replication_rows,
                "replication_slots": slot_rows,
            },
            "summary": {
                "limit": safe_limit,
                "replica_count": len(replication_rows),
                "slot_count": len(slot_rows),
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _mask_email(value: str) -> str:
    local, domain = value.split("@", 1)
    prefix = local[:2] if len(local) > 2 else local[:1]
    return f"{prefix}{'*' * max(3, len(local) - len(prefix))}@{domain}"


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 7:
        return value
    masked = "*" * (len(digits) - 4) + digits[-4:]
    return masked


def _mask_card(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 12:
        return value
    return "*" * (len(digits) - 4) + digits[-4:]


def _mask_ssn(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 9:
        return value
    return "***-**-" + digits[-4:]


async def redaction_test(value: str):
    try:
        sample = (value or "").strip()
        if not sample:
            raise QueryValidationError("value is required for redaction_test")

        matches = []
        redacted = sample

        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", sample):
            redacted = _mask_email(sample)
            matches.append("email")
        elif re.fullmatch(r"\d{3}-?\d{2}-?\d{4}", sample):
            redacted = _mask_ssn(sample)
            matches.append("ssn")
        elif re.fullmatch(r"(?:\+?\d[\d\-\s().]{6,}\d)", sample):
            redacted = _mask_phone(sample)
            matches.append("phone")
        elif re.fullmatch(r"(?:\d[ -]?){12,19}", sample):
            redacted = _mask_card(sample)
            matches.append("payment_card")

        return {
            "ok": True,
            "result": {
                "input_length": len(sample),
                "matched_rules": matches,
                "redacted": redacted,
                "changed": redacted != sample,
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
