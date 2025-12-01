#!/usr/bin/env python3
"""
Simple MCP Client to test your Python MCP Server locally.

Usage:
    python3 test_client.py
"""

import subprocess
import json
import uuid
import time

# Start the MCP server process
proc = subprocess.Popen(
    ["python3", "cli.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

def send(msg):
    msg_json = json.dumps(msg)
    proc.stdin.write(msg_json + "\n")
    proc.stdin.flush()

def read():
    line = proc.stdout.readline().strip()
    if not line:
        return None
    return json.loads(line)

def rpc(method, params=None):
    req_id = str(uuid.uuid4())
    msg = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method
    }
    if params:
        msg["params"] = params

    send(msg)
    return req_id

print("🔌 MCP Local Test Client Started\n")
print("Commands:")
print("1. health")
print("2. uptime")
print("3. schema")
print("4. sql")
print("5. safe")
print("6. explain")
print("7. stats")
print("8. slow")
print("exit to quit\n")

while True:
    cmd = input("mcp> ").strip().lower()

    if cmd == "exit":
        proc.terminate()
        break

    if cmd == "health":
        req_id = rpc("heartbeat")
    elif cmd == "uptime":
        req_id = rpc("uptime")
    elif cmd == "schema":
        req_id = rpc("get_schema")
    elif cmd == "sql":
        q = input("Enter SQL> ")
        req_id = rpc("sql_query", {"query": q})
    elif cmd == "safe":
        q = input("Enter SAFE SQL> ")
        req_id = rpc("sql_safe_query", {"query": q})
    elif cmd == "explain":
        q = input("Enter SQL> ")
        req_id = rpc("explain_query", {"query": q})
    elif cmd == "stats":
        req_id = rpc("table_stats")
    elif cmd == "slow":
        req_id = rpc("slow_queries")
    else:
        print("Unknown command")
        continue

    # Read response
    time.sleep(0.2)
    response = read()
    print("\n🔹 Response:")
    print(json.dumps(response, indent=2))
    print("\n")
