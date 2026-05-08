import sys
from mcp_server.otel import init_otel
from mcp_server.server import mcp

def main():
    try:
        # Use STDERR so STDIO protocol is not polluted
        sys.stderr.write("🚀 Starting postgres-mcp (STDIO mode)...\n")
        init_otel()
        mcp.run()
    except KeyboardInterrupt:
        # STDOUT may already be closed — STDERR is safe
        try:
            sys.stderr.write("🛑 postgres-mcp stopped gracefully.\n")
        except Exception:
            pass  # Safe exit when streams are closed

if __name__ == "__main__":
    main()
