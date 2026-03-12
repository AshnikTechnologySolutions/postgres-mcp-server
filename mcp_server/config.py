# mcp_server/config.py

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
