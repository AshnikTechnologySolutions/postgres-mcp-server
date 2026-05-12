import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI

import mcp_server.otel as otel_module


class OTelTests(unittest.TestCase):
    def tearDown(self):
        otel_module._OTEL_INITIALIZED = False

    def test_otel_disabled_by_default(self):
        # Explicitly remove OTEL_ENABLED so the test is not affected by any
        # .env file loaded earlier in the test session (e.g. .env.claude.local).
        with patch.dict(os.environ, {"OTEL_ENABLED": "false"}, clear=False):
            self.assertFalse(otel_module.otel_enabled())

    @patch("mcp_server.otel.FastAPIInstrumentor")
    @patch("mcp_server.otel.BatchSpanProcessor")
    @patch("mcp_server.otel.OTLPSpanExporter")
    @patch("mcp_server.otel.TracerProvider")
    @patch("mcp_server.otel.Resource")
    @patch("mcp_server.otel.trace")
    def test_init_otel_instruments_app_when_enabled(
        self,
        mock_trace,
        mock_resource,
        mock_tracer_provider,
        mock_exporter,
        mock_batch_processor,
        mock_fastapi_instrumentor,
    ):
        app = FastAPI()
        provider = mock_tracer_provider.return_value
        processor = mock_batch_processor.return_value
        provider.add_span_processor.return_value = None
        mock_resource.create.return_value = object()

        with patch.dict(
            os.environ,
            {
                "OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://127.0.0.1:4318/v1/traces",
            },
            clear=False,
        ):
            otel_module.init_otel(app)

        provider.add_span_processor.assert_called_once_with(processor)
        mock_trace.set_tracer_provider.assert_called_once_with(provider)
        mock_fastapi_instrumentor.instrument_app.assert_called_once()
