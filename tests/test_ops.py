import asyncio
import unittest
from unittest.mock import patch

from mcp_server.tools import ops as ops_module


class OpsToolTests(unittest.TestCase):
    def test_config_status_masks_secrets_but_reports_runtime_flags(self):
        with patch.dict(
            "os.environ",
            {
                "DB_POOL_MIN_SIZE": "3",
                "DB_POOL_MAX_SIZE": "9",
                "DB_CONNECT_TIMEOUT_SECONDS": "7",
                "AUDIT_LOG_PATH": "audit.jsonl",
                "MCP_HTTP_API_KEY": "set",
                "OTEL_ENABLED": "true",
                "OTEL_SERVICE_NAME": "postgres-mcp-server",
                "OTEL_ENVIRONMENT": "prod",
            },
            clear=False,
        ):
            result = asyncio.run(ops_module.config_status())

        self.assertTrue(result["ok"])
        self.assertEqual(result["config"]["db_pool_min_size"], 3)
        self.assertEqual(result["config"]["db_pool_max_size"], 9)
        self.assertTrue(result["config"]["mcp_http_api_key_enabled"])
        self.assertTrue(result["config"]["otel_enabled"])

    def test_audit_summary_aggregates_recent_events(self):
        events = [
            {"tool_name": "health", "ok": True},
            {"tool_name": "health", "ok": False, "error": "db timeout"},
            {"tool_name": "schema", "ok": False, "error": "db timeout"},
        ]
        with patch("mcp_server.tools.ops.read_audit_events", return_value=events):
            result = asyncio.run(ops_module.audit_summary(limit=10))

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["calls_by_tool"]["health"], 2)
        self.assertEqual(result["summary"]["failures_by_tool"]["schema"], 1)
        self.assertEqual(result["summary"]["top_errors"][0]["error"], "db timeout")

    def test_pool_status_uses_describe_pools(self):
        with patch("mcp_server.tools.ops.get_pool") as mock_get_pool:
            with patch("mcp_server.tools.ops.describe_pools", return_value={"read": {"initialized": True, "idle": 1}}):
                result = asyncio.run(ops_module.pool_status())

        self.assertTrue(result["ok"])
        self.assertIn("read", result["pools"])
        mock_get_pool.assert_called_once_with(role="read")

    def test_access_scope_reports_visible_objects(self):
        rows = [
            {"table_schema": "public", "table_name": "customers", "can_select": True},
            {"table_schema": "hr", "table_name": "employees", "can_select": False},
        ]
        with patch("mcp_server.tools.ops.fetch_rows", return_value=rows):
            result = asyncio.run(ops_module.access_scope(limit=50))

        self.assertTrue(result["ok"])
        self.assertEqual(result["scope"]["schema_count"], 1)
        self.assertEqual(result["scope"]["visible_object_count"], 1)
        self.assertEqual(result["scope"]["objects"][0]["table_name"], "customers")

    def test_readiness_degrades_when_extension_missing(self):
        health_rows = [
            {
                "database_name": "mcp_demo",
                "database_user": "mcpuser",
                "postgres_version": "PostgreSQL 17",
            }
        ]
        with patch("mcp_server.tools.ops.fetch_rows", return_value=health_rows):
            with patch("mcp_server.tools.ops.detect_pg_stat_statements_columns", side_effect=RuntimeError("missing extension")):
                result = asyncio.run(ops_module.readiness())

        # db is up, so ok=True; extension missing → status=degraded, not unavailable
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(result["checks"]["database"]["ok"])
        self.assertFalse(result["checks"]["pg_stat_statements"]["ok"])

    def test_locks_reports_blocked_sessions(self):
        rows = [
            {
                "blocked_pid": 101,
                "blocking_pid": 202,
                "blocked_query": "select * from orders",
            }
        ]
        with patch("mcp_server.tools.ops.fetch_rows", return_value=rows):
            result = asyncio.run(ops_module.locks(limit=10))

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["blocked_session_count"], 1)
        self.assertEqual(result["locks"][0]["blocking_pid"], 202)

    def test_index_usage_summarizes_usage_states(self):
        rows = [
            {"usage_state": "unused", "index_name": "idx_a"},
            {"usage_state": "active", "index_name": "idx_b"},
            {"usage_state": "unused", "index_name": "idx_c"},
        ]
        with patch("mcp_server.tools.ops.fetch_rows", return_value=rows):
            result = asyncio.run(ops_module.index_usage(limit=10))

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["usage_state_counts"]["unused"], 2)
        self.assertEqual(result["summary"]["returned"], 3)

    def test_vacuum_status_counts_tables_with_dead_tuples(self):
        rows = [
            {"table_name": "orders", "n_dead_tup": 15},
            {"table_name": "customers", "n_dead_tup": 0},
        ]
        with patch("mcp_server.tools.ops.fetch_rows", return_value=rows):
            result = asyncio.run(ops_module.vacuum_status(limit=10))

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["tables_with_dead_tuples"], 1)

    def test_replication_status_reports_replicas_and_slots(self):
        fetch_side_effect = [
            [{"in_recovery": False, "current_lsn": "0/123"}],
            [{"pid": 11, "application_name": "replica-a"}],
            [{"slot_name": "slot_a", "active": True}],
        ]
        with patch("mcp_server.tools.ops.fetch_rows", side_effect=fetch_side_effect):
            result = asyncio.run(ops_module.replication_status(limit=10))

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["replica_count"], 1)
        self.assertEqual(result["summary"]["slot_count"], 1)

    def test_redaction_test_masks_common_sensitive_values(self):
        email_result = asyncio.run(ops_module.redaction_test("alice@example.com"))
        ssn_result = asyncio.run(ops_module.redaction_test("123-45-6789"))

        self.assertTrue(email_result["ok"])
        self.assertIn("email", email_result["result"]["matched_rules"])
        self.assertTrue(email_result["result"]["changed"])

        self.assertTrue(ssn_result["ok"])
        self.assertEqual(ssn_result["result"]["redacted"], "***-**-6789")
