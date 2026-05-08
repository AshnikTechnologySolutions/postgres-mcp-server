import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("postgres-mcp")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.INFO)

DEFAULT_DB = os.getenv("DEFAULT_DB", "local").strip().lower()
ALLOW_ARBITRARY_SQL = os.getenv("ALLOW_ARBITRARY_SQL", "false").strip().lower() == "true"

DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
DB_CONNECT_TIMEOUT_SECONDS = float(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))

MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "2000"))

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "mcp_audit.log")
AUDIT_LOG_MAX_QUERY_PREVIEW = int(os.getenv("AUDIT_LOG_MAX_QUERY_PREVIEW", "240"))

MCP_HTTP_API_KEY_ENABLED = bool(os.getenv("MCP_HTTP_API_KEY"))

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").strip().lower() == "true"
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "postgres-mcp-server")
OTEL_SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
OTEL_ENVIRONMENT = os.getenv("OTEL_ENVIRONMENT", "development")
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:4318/v1/traces"
)
