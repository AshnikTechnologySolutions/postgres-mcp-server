import asyncio
import unittest
from unittest.mock import patch

from mcp_server import audit as audit_module
from mcp_server.request_context import reset_request_id, set_request_id


class AuditTests(unittest.TestCase):
    def test_log_audit_event_includes_request_and_trace_context(self):
        token = set_request_id("req-123")
        captured = {}

        def fake_write(event):
            captured.update(event)

        try:
            with patch("mcp_server.audit.current_trace_context", return_value={"trace_id": "trace-abc", "span_id": "span-def"}):
                with patch("mcp_server.audit._write_event_sync", side_effect=fake_write):
                    asyncio.run(
                        audit_module.log_audit_event(
                            tool_name="health",
                            ok=True,
                            transport="http",
                            details={"path": "/healthz"},
                        )
                    )
        finally:
            reset_request_id(token)

        self.assertEqual(captured["request_id"], "req-123")
        self.assertEqual(captured["trace_id"], "trace-abc")
        self.assertEqual(captured["span_id"], "span-def")
        self.assertEqual(captured["level"], "info")
        self.assertEqual(captured["details"]["path"], "/healthz")
