# mcp_server/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Read default DB target: local | remote
DEFAULT_DB = os.getenv("DEFAULT_DB", "local").strip().lower()

# Safety flag for SQL execution (read-only or full)
ALLOW_ARBITRARY_SQL = os.getenv("ALLOW_ARBITRARY_SQL", "false").lower() == "true"

# Database URLs are now resolved in mcp_server/db.py according to user role.

print("🔧 Role-based database mode enabled (database URLs resolved in db.py)")
print(f"🔒 ALLOW_ARBITRARY_SQL = {ALLOW_ARBITRARY_SQL}")