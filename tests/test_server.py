import unittest
from unittest.mock import MagicMock, patch

from mcp_server.request_context import get_request_id
from mcp_server.server import _mcp_tool_span


class ServerTracingTests(unittest.TestCase):
    @patch("mcp_server.server.generate_request_id", return_value="mcp-req-123")
    @patch("mcp_server.server.get_tracer")
    def test_mcp_tool_span_sets_request_context(self, mock_get_tracer, _mock_request_id):
        fake_span = MagicMock()
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_span
        fake_context.__exit__.return_value = None
        fake_tracer = MagicMock()
        fake_tracer.start_as_current_span.return_value = fake_context
        mock_get_tracer.return_value = fake_tracer

        with _mcp_tool_span("health", {"limit": 10}):
            self.assertEqual(get_request_id(), "mcp-req-123")

        fake_tracer.start_as_current_span.assert_called_once_with("mcp.health")
        fake_span.set_attribute.assert_any_call("mcp.transport", "stdio")
        fake_span.set_attribute.assert_any_call("mcp.tool_name", "health")
        fake_span.set_attribute.assert_any_call("mcp.request_id", "mcp-req-123")
        fake_span.set_attribute.assert_any_call("mcp.limit", 10)
