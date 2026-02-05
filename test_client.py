#!/usr/bin/env python3
"""
Fully working RAW MCP client for FastMCP 2.x
Correctly uses tools/call wrapper
Matches YOUR actual server tools.
"""

import subprocess
import json
import uuid
import threading
import queue
import sys
import time

# ─────────────────────────────
# Start server process
# ─────────────────────────────
proc = subprocess.Popen(
    ["python3", "cli.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

print("🔌 MCP Raw Test Client Started\n")

out_q = queue.Queue()
err_q = queue.Queue()

def reader_thread(stream, q):
    for line in iter(stream.readline, ""):
        if line:
            q.put(line)
    stream.close()

threading.Thread(target=reader_thread, args=(proc.stdout, out_q), daemon=True).start()
threading.Thread(target=reader_thread, args=(proc.stderr, err_q), daemon=True).start()

# ─────────────────────────────
# Low-level helpers
# ─────────────────────────────

def send_json(msg):
    raw = json.dumps(msg)
    proc.stdin.write(raw + "\n")
    proc.stdin.flush()

def wait_for_response(req_id, timeout=3):
    start = time.time()
    while time.time() - start < timeout:
        # stderr logs
        try:
            while True:
                e = err_q.get_nowait().strip()
                if e:
                    print(f"⚠️  [server stderr] {e}")
        except queue.Empty:
            pass

        # stdout messages
        try:
            line = out_q.get_nowait().strip()
        except queue.Empty:
            time.sleep(0.05)
            continue

        if not line:
            continue
        
        try:
            msg = json.loads(line)
        except:
            print(f"🔸 Non-JSON output: {line}")
            continue

        if msg.get("id") == req_id:
            return msg

    return None

# ─────────────────────────────
# 1) Send initialize
# ─────────────────────────────
init_id = str(uuid.uuid4())
send_json({
    "jsonrpc": "2.0",
    "id": init_id,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "local-test-client", "version": "1.0"}
    }
})

print("🔄 Sending initialize handshake...")
resp = wait_for_response(init_id)
print("\n🟢 Initialization Response:")
print(json.dumps(resp, indent=2), "\n")


# ─────────────────────────────
# MCP tools/call wrapper
# ─────────────────────────────

def call_tool(tool_name, arguments=None):
    req_id = str(uuid.uuid4())
    msg = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {}
        }
    }

    send_json(msg)
    return req_id


# ─────────────────────────────
# Valid tool names (from inspect)
# ─────────────────────────────
VALID_TOOLS = [
    "health",
    "uptime",
    "sql_query",
    "sql_safe",
    "table_stats",
    "slow_queries",
    "explain_query"
]

print("Available commands:")
for t in VALID_TOOLS:
    print("  ", t)
print("  exit\n")


# ─────────────────────────────
# REPL LOOP
# ─────────────────────────────
try:
    while True:
        cmd = input("mcp> ").strip().lower()

        if cmd == "exit":
            print("👋 Exiting...")
            proc.terminate()
            sys.exit(0)

        elif cmd == "health":
            rid = call_tool("health")

        elif cmd == "uptime":
            rid = call_tool("uptime")

        elif cmd == "table_stats":
            rid = call_tool("table_stats", {"limit": 10})

        elif cmd == "slow_queries":
            rid = call_tool("slow_queries", {"limit": 5})

        elif cmd == "sql_query" or cmd == "sql":
            q = input("SQL> ")
            rid = call_tool("sql_query", {"query": q})

        elif cmd == "sql_safe" or cmd == "safe":
            q = input("SAFE SQL> ")
            rid = call_tool("sql_safe", {"query": q})

        elif cmd == "explain_query" or cmd == "explain":
            q = input("SQL> ")
            rid = call_tool("explain_query", {"query": q, "analyze": False})

        else:
            print("❓ Unknown or unsupported command")
            print("Valid:", VALID_TOOLS)
            continue

        print("⏳ Waiting for response...")
        resp = wait_for_response(rid)

        print("\n🔹 Response:")
        print(json.dumps(resp, indent=2), "\n")

except KeyboardInterrupt:
    print("\n👋 Interrupted")
    proc.terminate()
    sys.exit(0)