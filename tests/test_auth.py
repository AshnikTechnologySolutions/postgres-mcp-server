import asyncio
import os
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from mcp_server.auth import require_request_api_key


class AuthTests(unittest.TestCase):
    def _make_request(self, api_key: str | None = None) -> MagicMock:
        request = MagicMock()
        request.headers.get.return_value = api_key
        return request

    def test_no_key_configured_allows_all_requests(self):
        env = {k: v for k, v in os.environ.items() if k != "MCP_HTTP_API_KEY"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            asyncio.run(require_request_api_key(self._make_request()))

    def test_correct_key_passes(self):
        with unittest.mock.patch.dict(os.environ, {"MCP_HTTP_API_KEY": "secret-key"}, clear=False):
            asyncio.run(require_request_api_key(self._make_request(api_key="secret-key")))

    def test_wrong_key_raises_401(self):
        with unittest.mock.patch.dict(os.environ, {"MCP_HTTP_API_KEY": "secret-key"}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_request_api_key(self._make_request(api_key="wrong-key")))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_missing_key_raises_401(self):
        with unittest.mock.patch.dict(os.environ, {"MCP_HTTP_API_KEY": "secret-key"}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_request_api_key(self._make_request(api_key=None)))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_key_raises_401(self):
        with unittest.mock.patch.dict(os.environ, {"MCP_HTTP_API_KEY": "secret-key"}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_request_api_key(self._make_request(api_key="")))
            self.assertEqual(ctx.exception.status_code, 401)
