import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from mcp_server.http_app import app


class HttpAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_healthz(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")

    def test_readyz(self):
        with patch("mcp_server.http_app.readiness_check", new_callable=AsyncMock) as mock_readiness:
            mock_readiness.return_value = {"ok": True, "status": "ready"}
            response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertIn("x-request-id", response.headers)

    def test_readyz_returns_503_when_readiness_fails(self):
        with patch("mcp_server.http_app.readiness_check", new_callable=AsyncMock) as mock_readiness:
            mock_readiness.return_value = {"ok": False, "status": "degraded", "checks": {"database": {"ok": False}}}
            response = self.client.get("/readyz")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")

    @patch("mcp_server.router.require_request_api_key", new_callable=AsyncMock)
    @patch("mcp_server.router.health_check", new_callable=AsyncMock)
    def test_root_route_uses_registered_health_handler(self, mock_health_check, mock_require_api_key):
        mock_health_check.return_value = {"ok": True, "service": "test"}

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "service": "test"})
        mock_require_api_key.assert_awaited()
        mock_health_check.assert_awaited()

    def test_request_id_header_passthrough(self):
        response = self.client.get("/healthz", headers={"x-request-id": "req-test-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "req-test-123")

    def test_protected_route_returns_401_without_api_key(self):
        with patch.dict(os.environ, {"MCP_HTTP_API_KEY": "test-secret"}, clear=False):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 401)

    def test_protected_route_returns_401_with_wrong_api_key(self):
        with patch.dict(os.environ, {"MCP_HTTP_API_KEY": "test-secret"}, clear=False):
            response = self.client.get("/", headers={"x-api-key": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_protected_route_passes_with_correct_api_key(self):
        with patch.dict(os.environ, {"MCP_HTTP_API_KEY": "test-secret"}, clear=False):
            with patch("mcp_server.router.health_check", new_callable=AsyncMock) as mock_health:
                mock_health.return_value = {"ok": True, "status": "running"}
                response = self.client.get("/", headers={"x-api-key": "test-secret"})
        self.assertEqual(response.status_code, 200)
