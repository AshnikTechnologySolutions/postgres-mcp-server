"""
Integration tests against the local PostgreSQL instance.

Requires .env.claude.local in the project root with LOCAL_*_DATABASE_URL set,
or those env vars exported in the shell.

Run with:
  python -m pytest tests/test_integration.py -v
"""
import os
import sys
import unittest
from pathlib import Path

from dotenv import load_dotenv

# Load .env.claude.local so db.py picks up LOCAL_* DSNs
_env_file = Path(__file__).parent.parent / ".env.claude.local"
if _env_file.exists():
    load_dotenv(_env_file, override=True)

# Guard: skip the whole module when the local DB is not configured
_read_url = os.getenv("LOCAL_READ_DATABASE_URL", "")
if not _read_url:
    print("Skipping integration tests: LOCAL_READ_DATABASE_URL not set", file=sys.stderr)
    sys.exit(0)

import asyncpg  # noqa: E402

try:
    import asyncio
    asyncio.run(asyncpg.connect(_read_url, timeout=3))
    _DB_REACHABLE = True
except Exception as _e:
    _DB_REACHABLE = False
    print(f"Skipping integration tests: cannot connect to local DB — {_e}", file=sys.stderr)

# Check whether pg_stat_statements is actually queryable (needs shared_preload_libraries).
_PG_STAT_AVAILABLE = False
if _DB_REACHABLE:
    async def _check_pg_stat():
        conn = await asyncpg.connect(_read_url, timeout=3)
        try:
            await conn.fetchval("SELECT count(*) FROM pg_stat_statements LIMIT 1")
            return True
        except Exception:
            return False
        finally:
            await conn.close()
    _PG_STAT_AVAILABLE = asyncio.run(_check_pg_stat())


def _clear_pools():
    """Drop stale asyncpg pool objects from the previous event loop."""
    from mcp_server import db
    db._POOLS.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from mcp_server.tools.health import health_check, uptime_check          # noqa: E402
from mcp_server.tools.schema import get_schema                           # noqa: E402
from mcp_server.tools.stats import slow_queries, table_stats             # noqa: E402
from mcp_server.tools.explain import explain_query                       # noqa: E402
from mcp_server.tools.index_advisor import index_advisor                 # noqa: E402
from mcp_server.tools.audit import audit_logs                            # noqa: E402
from mcp_server.tools.ops import (                                       # noqa: E402
    access_scope,
    audit_summary,
    config_status,
    index_usage,
    locks,
    pool_status,
    readiness,
    replication_status,
    vacuum_status,
)
from mcp_server.sql import fetch_rows, normalize_query                   # noqa: E402


# ---------------------------------------------------------------------------
# Base class: fresh event loop + fresh pool per test method
# ---------------------------------------------------------------------------

@unittest.skipUnless(_DB_REACHABLE, "local PostgreSQL not reachable")
class IntegrationBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _clear_pools()


# ---------------------------------------------------------------------------
# Health / uptime
# ---------------------------------------------------------------------------

class IntegrationHealthTests(IntegrationBase):

    async def test_health_check_returns_postgres_version(self):
        result = await health_check()
        self.assertTrue(result["ok"], result)
        self.assertIn("PostgreSQL", result["postgres_version"])
        self.assertEqual(result["database_name"], "mcp_demo")
        self.assertEqual(result["database_user"], "mcpuser")

    async def test_uptime_check_returns_positive_uptime(self):
        result = await uptime_check()
        self.assertTrue(result["ok"], result)
        self.assertIn("start_time", result)
        self.assertIn("uptime", result)
        self.assertTrue(result["uptime"])


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class IntegrationSchemaTests(IntegrationBase):

    async def test_get_schema_returns_known_tables(self):
        result = await get_schema()
        self.assertTrue(result["ok"], result)
        self.assertIn("customers", result["schema"])
        self.assertIn("categories", result["schema"])

    async def test_schema_columns_have_required_fields(self):
        result = await get_schema()
        self.assertTrue(result["ok"], result)
        for table, columns in result["schema"].items():
            for col in columns:
                self.assertIn("column_name", col, f"table {table}")
                self.assertIn("data_type", col, f"table {table}")
                self.assertIn("is_nullable", col, f"table {table}")


# ---------------------------------------------------------------------------
# sql_safe (via fetch_rows with read_only=True)
# ---------------------------------------------------------------------------

class IntegrationSqlSafeTests(IntegrationBase):

    async def test_simple_select_returns_rows(self):
        sql = normalize_query("SELECT id, email FROM customers LIMIT 5")
        rows = await fetch_rows(sql, role="read", read_only=True)
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 5)
        for row in rows:
            self.assertIn("id", row)
            self.assertIn("email", row)

    async def test_count_query_returns_single_row(self):
        sql = normalize_query("SELECT count(*) AS total FROM customers")
        rows = await fetch_rows(sql, role="read", read_only=True)
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["total"], 0)

    async def test_write_blocked_in_read_only_transaction(self):
        sql = normalize_query("INSERT INTO customers(email) VALUES ('x@x.com')")
        with self.assertRaises(asyncpg.ReadOnlySQLTransactionError):
            await fetch_rows(sql, role="read", read_only=True)

    async def test_select_with_semicolon_in_string_literal(self):
        sql = normalize_query("SELECT 'hello;world' AS val")
        rows = await fetch_rows(sql, role="read", read_only=True)
        self.assertEqual(rows[0]["val"], "hello;world")

    async def test_max_result_rows_cap_respected(self):
        # Default MAX_RESULT_ROWS=2000; customers has 2000 rows — fetch all
        sql = normalize_query("SELECT id FROM customers")
        rows = await fetch_rows(sql, role="read", read_only=True)
        self.assertLessEqual(len(rows), int(os.getenv("MAX_RESULT_ROWS", "2000")))


# ---------------------------------------------------------------------------
# table_stats
# ---------------------------------------------------------------------------

class IntegrationTableStatsTests(IntegrationBase):

    async def test_table_stats_returns_known_tables(self):
        result = await table_stats(limit=20)
        self.assertTrue(result["ok"], result)
        names = [row["table_name"] for row in result["stats"]]
        self.assertIn("customers", names)

    async def test_table_stats_has_required_fields(self):
        result = await table_stats(limit=5)
        self.assertTrue(result["ok"], result)
        for row in result["stats"]:
            self.assertIn("table_name", row)
            self.assertIn("est_rows", row)
            self.assertIn("total_size", row)

    async def test_table_stats_respects_limit(self):
        result = await table_stats(limit=3)
        self.assertTrue(result["ok"], result)
        self.assertLessEqual(len(result["stats"]), 3)


# ---------------------------------------------------------------------------
# slow_queries
# ---------------------------------------------------------------------------

@unittest.skipUnless(_PG_STAT_AVAILABLE, "pg_stat_statements not loaded via shared_preload_libraries")
class IntegrationSlowQueriesTests(IntegrationBase):

    async def test_slow_queries_returns_list(self):
        result = await slow_queries(limit=5)
        self.assertTrue(result["ok"], result)
        self.assertIsInstance(result["slow_queries"], list)

    async def test_slow_queries_rows_have_required_fields(self):
        result = await slow_queries(limit=5)
        self.assertTrue(result["ok"], result)
        for row in result["slow_queries"]:
            self.assertIn("query", row)
            self.assertIn("calls", row)
            self.assertIn("total_exec_time_ms", row)
            self.assertIn("mean_exec_time_ms", row)

    async def test_slow_queries_respects_limit(self):
        result = await slow_queries(limit=3)
        self.assertTrue(result["ok"], result)
        self.assertLessEqual(len(result["slow_queries"]), 3)


# ---------------------------------------------------------------------------
# explain_query
# ---------------------------------------------------------------------------

class IntegrationExplainTests(IntegrationBase):

    async def test_explain_returns_plan(self):
        result = await explain_query("SELECT * FROM customers LIMIT 1")
        self.assertTrue(result["ok"], result)
        self.assertIn("plan", result)
        self.assertIsInstance(result["plan"], list)

    async def test_explain_plan_has_node_type(self):
        result = await explain_query("SELECT id FROM customers LIMIT 10")
        self.assertTrue(result["ok"], result)
        plan_root = result["plan"][0]["Plan"]
        self.assertIn("Node Type", plan_root)

    async def test_explain_analyze_is_blocked(self):
        result = await explain_query("SELECT 1", analyze=True)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())

    async def test_explain_rejects_dml(self):
        result = await explain_query("DELETE FROM customers WHERE id = 1")
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# index_advisor
# ---------------------------------------------------------------------------

class IntegrationIndexAdvisorTests(IntegrationBase):

    async def test_index_advisor_returns_recommendations(self):
        result = await index_advisor("SELECT * FROM customers LIMIT 1")
        self.assertTrue(result["ok"], result)
        self.assertIn("recommendations", result)
        self.assertIsInstance(result["recommendations"], list)
        self.assertGreater(len(result["recommendations"]), 0)

    async def test_index_advisor_rejects_dml(self):
        result = await index_advisor("DELETE FROM customers WHERE id = 1")
        self.assertFalse(result["ok"])

    async def test_index_advisor_rejects_empty_query(self):
        result = await index_advisor("")
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------

class IntegrationReadinessTests(IntegrationBase):

    async def test_readiness_ok_when_db_connected(self):
        result = await readiness()
        # DB is up → ok must be True regardless of extension state
        self.assertTrue(result["ok"], result)
        self.assertIn(result["status"], ("ready", "degraded"))

    async def test_readiness_database_check_has_version(self):
        result = await readiness()
        db_check = result["checks"]["database"]
        self.assertTrue(db_check["ok"])
        self.assertIn("postgres_version", db_check)
        self.assertIn("database_name", db_check)

    async def test_readiness_ready_when_extension_present(self):
        result = await readiness()
        if result["checks"]["pg_stat_statements"]["ok"]:
            self.assertEqual(result["status"], "ready")


# ---------------------------------------------------------------------------
# audit_logs
# ---------------------------------------------------------------------------

class IntegrationAuditLogsTests(IntegrationBase):

    async def test_audit_logs_returns_list(self):
        result = await audit_logs(limit=10)
        self.assertTrue(result["ok"], result)
        self.assertIsInstance(result["events"], list)

    async def test_audit_logs_respects_limit(self):
        result = await audit_logs(limit=3)
        self.assertTrue(result["ok"], result)
        self.assertLessEqual(len(result["events"]), 3)

    async def test_audit_logs_filter_by_nonexistent_tool_returns_empty(self):
        result = await audit_logs(limit=20, tool_name="__nonexistent__")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["events"], [])

    async def test_audit_logs_filter_by_ok_false_returns_only_errors(self):
        result = await audit_logs(limit=50, ok=False)
        self.assertTrue(result["ok"], result)
        for event in result["events"]:
            self.assertFalse(event["ok"])


# ---------------------------------------------------------------------------
# ops tools
# ---------------------------------------------------------------------------

class IntegrationOpsTests(IntegrationBase):

    async def test_pool_status_shows_read_pool(self):
        await fetch_rows("SELECT 1", role="read", read_only=True)
        result = await pool_status()
        self.assertTrue(result["ok"], result)
        self.assertIn("read", result["pools"])

    async def test_access_scope_lists_customers(self):
        result = await access_scope(limit=100)
        self.assertTrue(result["ok"], result)
        names = [o["table_name"] for o in result["scope"]["objects"]]
        self.assertIn("customers", names)

    async def test_locks_returns_list(self):
        result = await locks(limit=10)
        self.assertTrue(result["ok"], result)
        self.assertIsInstance(result["locks"], list)

    async def test_index_usage_returns_list(self):
        result = await index_usage(limit=20)
        self.assertTrue(result["ok"], result)
        self.assertIsInstance(result["indexes"], list)

    async def test_index_usage_usage_state_values(self):
        result = await index_usage(limit=50)
        self.assertTrue(result["ok"], result)
        valid_states = {"unused", "low", "active"}
        for row in result["indexes"]:
            self.assertIn(row["usage_state"], valid_states)

    async def test_vacuum_status_returns_tables(self):
        result = await vacuum_status(limit=10)
        self.assertTrue(result["ok"], result)
        self.assertIsInstance(result["tables"], list)

    async def test_vacuum_status_dead_tuple_pct_is_numeric(self):
        result = await vacuum_status(limit=10)
        self.assertTrue(result["ok"], result)
        for row in result["tables"]:
            self.assertIn("dead_tuple_pct", row)

    async def test_replication_status_has_instance_info(self):
        result = await replication_status()
        self.assertTrue(result["ok"], result)
        self.assertIn("instance", result["replication"])
        self.assertIn("in_recovery", result["replication"]["instance"])
        self.assertIn("replicas", result["replication"])
        self.assertIn("replication_slots", result["replication"])

    async def test_config_status_returns_known_keys(self):
        result = await config_status()
        self.assertTrue(result["ok"], result)
        cfg = result["config"]
        for key in ("default_db", "allow_arbitrary_sql", "max_result_rows",
                    "db_pool_min_size", "db_pool_max_size", "audit_log_path"):
            self.assertIn(key, cfg, f"missing key: {key}")

    async def test_audit_summary_returns_aggregates(self):
        result = await audit_summary(limit=50)
        self.assertTrue(result["ok"], result)
        for key in ("calls_by_tool", "failures_by_tool", "top_errors"):
            self.assertIn(key, result["summary"], f"missing key: {key}")
