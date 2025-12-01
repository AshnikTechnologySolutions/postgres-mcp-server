#!/usr/bin/env python3
"""
Robust subprocess-based MCP JSON-RPC test client.

Works without depending on FastMCP's client transports API (avoids import issues).
Starts your CLI MCP server (cli.py) in a subprocess, sends JSON-RPC lines and
waits for matching responses by id.

Usage:
    python3 test_client.py
"""

import subprocess
import json
import uuid
import time
import threading
import queue
import sys
from typing import Optional

SERVER_CMD = ["python3", "cli.py"]  # adjust if you run differently
SERVER_CWD = "."                     # repo root where cli.py lives
READ_TIMEOUT = 10                    # seconds to wait for a response


# Threaded stdout reader: pushes JSON messages into a queue
def _reader_thread(proc, out_q: queue.Queue, err_q: queue.Queue):
    while True:
        line = proc.stdout.readline()
        if line == "" and proc.poll() is not None:
            break
        if not line:
            time.sleep(0.01)
            continue
        line = line.strip()
        if not line:
            continue

        # Try to parse JSON; if that fails, push raw to err queue
        try:
            data = json.loads(line)
            out_q.put(data)
        except Exception:
            # Keep stderr-like outputs separate for debugging
            err_q.put(line)

    # drain remaining stderr if any
    for l in proc.stderr:
        err_q.put(l.strip())


class MCPTestClient:
    def __init__(self, cmd=SERVER_CMD, cwd=SERVER_CWD):
        self.cmd = cmd
        self.cwd = cwd
        self.proc: Optional[subprocess.Popen] = None
        self._out_q = queue.Queue()
        self._err_q = queue.Queue()
        self._responses = {}  # id -> response
        self._lock = threading.Lock()
        self._reader = None

    def start_server(self):
        # Start MCP server subprocess
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Start reader thread
        self._reader = threading.Thread(target=_reader_thread, args=(self.proc, self._out_q, self._err_q), daemon=True)
        self._reader.start()

        # Background thread to dispatch responses to self._responses
        threading.Thread(target=self._dispatch_loop, daemon=True).start()

    def _dispatch_loop(self):
        while True:
            try:
                msg = self._out_q.get(timeout=0.1)
            except queue.Empty:
                if self.proc and self.proc.poll() is not None:
                    break
                continue

            # If it's a JSON-RPC response with id, store it
            if isinstance(msg, dict) and "id" in msg:
                with self._lock:
                    self._responses[msg["id"]] = msg
            else:
                # put non-RPC messages into err queue for debugging
                self._err_q.put(json.dumps(msg))

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    def send_jsonrpc(self, method: str, params: Optional[dict] = None, timeout=READ_TIMEOUT):
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("Server process is not running")

        req_id = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        # IMPORTANT: FastMCP expects `params` for tools even when empty `{}`.
        payload["params"] = params if params is not None else {}

        # write line
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        self.proc.stdin.write(raw + "\n")
        self.proc.stdin.flush()

        # wait for response with the same id
        start = time.time()
        while True:
            with self._lock:
                if req_id in self._responses:
                    return self._responses.pop(req_id)

            # show any helpful stderr lines from server for debugging
            try:
                err_line = self._err_q.get_nowait()
                print("SERVER:", err_line, file=sys.stderr)
            except queue.Empty:
                pass

            if time.time() - start > timeout:
                raise TimeoutError(f"No response within {timeout}s for id {req_id}")

            time.sleep(0.05)


def interactive_loop(client: MCPTestClient):
    banner = """
🔌 MCP Local Test Client
Available commands:
  health        -> basic health (send empty params {})
  uptime        -> uptime (send empty params {})
  schema        -> get_schema (send empty params {})
  sql           -> sql_query (asks for SQL, sends {"query": "..."})
  safe          -> sql_safe (asks for SQL, sends {"query": "..."})
  explain       -> explain_query (asks for SQL, sends {"query": "...", "analyze": false})
  table_stats   -> table_stats (optional {"limit": N})
  slow_queries  -> slow_queries (optional {"limit": N})
  exit
"""
    print(banner)

    try:
        while True:
            cmd = input("mcp> ").strip().lower()
            if not cmd:
                continue
            if cmd == "exit":
                break

            try:
                if cmd == "health":
                    resp = client.send_jsonrpc("health", {})
                elif cmd == "uptime":
                    resp = client.send_jsonrpc("uptime", {})
                elif cmd == "schema":
                    resp = client.send_jsonrpc("get_schema", {})
                elif cmd == "sql":
                    q = input("Enter SQL> ").strip()
                    resp = client.send_jsonrpc("sql_query", {"query": q})
                elif cmd == "safe":
                    q = input("Enter SAFE SQL> ").strip()
                    resp = client.send_jsonrpc("sql_safe", {"query": q})
                elif cmd == "explain":
                    q = input("Enter SQL> ").strip()
                    analyze = input("Analyze? (y/N)> ").strip().lower() == "y"
                    resp = client.send_jsonrpc("explain_query", {"query": q, "analyze": analyze})
                elif cmd == "table_stats":
                    lim = input("Limit (enter for default)> ").strip()
                    params = {"limit": int(lim)} if lim else {}
                    resp = client.send_jsonrpc("table_stats", params)
                elif cmd == "slow_queries":
                    lim = input("Limit (enter for default)> ").strip()
                    params = {"limit": int(lim)} if lim else {}
                    resp = client.send_jsonrpc("slow_queries", params)
                else:
                    print("Unknown command")
                    continue

                print("\n🔹 Response:")
                print(json.dumps(resp, indent=2, ensure_ascii=False))
                print("\n")
            except TimeoutError as te:
                print("❌ Timeout:", te)
            except Exception as e:
                print("❌ Error:", e)

    finally:
        client.stop()


if __name__ == "__main__":
    c = MCPTestClient()
    c.start_server()

    # give the server a second to startup and emit any logs
    time.sleep(0.8)

    interactive_loop(c)