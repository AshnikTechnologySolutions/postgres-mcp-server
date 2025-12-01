# 🚀 AI-Enhanced PostgreSQL MCP Server  
![Architecture](./assets/architecture.png)
A full-featured **Model Context Protocol (MCP) Server** written entirely in **Python**, enabling **Claude, ChatGPT, or any LLM agent** to securely interact with databases using natural language.

---

# 📌 Overview

This repository turns your PostgreSQL (and other data sources) into a **conversational AI knowledge engine**.

### 🧠 It enables:
- Natural-language SQL query generation  
- Schema-aware AI interactions  
- Real-time health checks  
- DB performance monitoring  
- Explain plan visualization  
- Safe SQL firewall  
- Multi-database routing  
- Claude Desktop as a live SQL assistant  

### 🎯 Ideal For:
- DBAs  
- Data engineers  
- AI developers  
- Analysts  
- Teams building AI copilots  
- Multi-DB integration layers  

---

# ✨ Features

## 🔍 1. Natural-Language SQL Assistant
- AI → SQL conversion with schema context  
- Auto schema refresh every 5 minutes  
- Pretty table formatting  
- Tool routing (intent detection)  
- Timing logs: MCP time, query time, RTT  

## 🛠️ 2. MCP Tools (Python)
The MCP server exposes the following tools:

| Tool Name | Description |
|-----------|-------------|
| `sql_query` | Full SQL access (read/write) |
| `sql_safe` | Read-only SQL with firewall |
| `explain` | Query plan (text/tree/json) |
| `health` | DB health, version, connections |
| `uptime` | Database uptime via pg_postmaster_start_time |
| `schema` | Live table/column metadata |
| `stats` | Row counts, table size, index usage |

## 🧩 3. Multi-Target Support
Already implemented for PostgreSQL.  
Extendable (plug-in architecture) to:

- MySQL via `aiomysql`
- MongoDB via `motor`
- Redis / Valkey via `aioredis`
- REST APIs using `httpx`
- Filesystem tools using Python I/O

## 🧬 4. Pure-Python Server (FastMCP)
- No Node.js  
- No Express  
- Extremely reliable MCP engine  
- First-class Claude Desktop compatibility  

## 🔒 5. Security
- .env-based secrets  
- No hardcoded credentials  
- Optional DB SSL  
- Read-only firewall (`sql_safe`)  
- Role-based PostgreSQL users  
- Isolation via Python virtual environment  

---

# 📦 Repository Structure

```
postgres-mcp-server/
├── cli.py                 # Starts MCP server (stdio transport)
├── requirements.txt       # Python dependencies
├── mcp_server/
│   ├── server.py          # FastMCP tool definitions
│   ├── config.py          # Loads DATABASE_URL
│   ├── db.py              # PostgreSQL async connection helper
│   ├── router.py          # (optional) tool registry
│   ├── tools/             # Tool implementations
│   │   ├── query.py
│   │   ├── safe_query.py
│   │   ├── schema.py
│   │   ├── stats.py
│   │   ├── explain.py
│   │   ├── uptime.py
│   │   └── health.py
└── test_client.py
```

---

# 🏗️ Installation

## 1️⃣ Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 2️⃣ Install Requirements

```bash
pip install -r requirements.txt
```

## 3️⃣ Configure Database URL

**Option A: export variable**

```bash
export DATABASE_URL="postgresql://mcpuser:mcppassword@localhost:5432/mcp_demo"
```

**Option B: .env file**

```
DATABASE_URL=postgresql://mcpuser:mcppassword@localhost:5432/mcp_demo
```

---

# 🚀 Run MCP Server

```bash
python3 cli.py
```

You should see:

```
FastMCP 2.x
Server: postgres-mcp
Transport: STDIO
Status: Running...
```

---

# 🧠 Connect with Claude Desktop (Local MCP Mode)

Create or update:

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add:

```json
{
  "mcpServers": {
    "postgres-mcp": {
      "type": "process",
      "command": "python3",
      "args": ["cli.py"],
      "cwd": "/Users/yourname/postgres-mcp-server",
      "env": {
        "DATABASE_URL": "postgresql://mcpuser:mcppassword@localhost:5432/mcp_demo"
      }
    }
  }
}
```

Restart Claude.

---

# 🎤 Example Questions Claude Can Answer

```
Top 10 customers by revenue
Uptime of my database
Show table stats
Explain: SELECT * FROM orders LIMIT 10
List all tables
Slowest queries
Schema for payments table
```

---

# 🛠 MCP Tools: Detailed Documentation

## 1. `sql_query`
Runs any SQL.

```json
{
  "tool": "sql_query",
  "query": "SELECT * FROM customers LIMIT 5;"
}
```

## 2. `sql_safe`
Blocks dangerous commands.

Blocked keywords:
```
insert, update, delete, alter, drop, truncate
```

## 3. `schema`
Returns tables + columns.

## 4. `stats`
Shows:
- row count  
- table size  
- index sizes  

## 5. `explain`
Returns EXPLAIN output.

## 6. `uptime`
Uses PostgreSQL internal:

```
SELECT now() - pg_postmaster_start_time();
```

## 7. `health`
Checks:
- PostgreSQL version  
- connection  
- uptime  

---

# 🧪 Test Client (local)

```bash
python3 test_client.py
```

---

# 🌐 Deployment Models

## 🔹 Model A — Everything on one VM  
(Your laptop or dev server)

## 🔹 Model B — 3-Tier  
```
VM-1 → Claude / Chatbot  
VM-2 → MCP Server  
VM-3 → PostgreSQL  
```

Firewall:

Postgres:
```
sudo ufw allow from <MCP_IP> to any port 5432
```

MCP:
```
sudo ufw allow from <CLIENT_IP> to any port 8000
```

---

# 🔐 Security Best Practices

| Layer | Protection |
|-------|------------|
| MCP server | no write operations via safe_query |
| Postgres | dedicated user with least privileges |
| Networking | firewall allow-list per host |
| Secrets | .env + chmod 600 |
| Claude | runs MCP in isolated subprocess |

---

# 🧩 Optional Extensions

You can add new targets easily.

## MySQL example

```python
import aiomysql

@mcp.tool()
async def mysql_query(query: str):
    conn = await aiomysql.connect(...)
    ...
```

## MongoDB example

```python
from motor.motor_asyncio import AsyncIOMotorClient
```

## REST API example

```python
import httpx
```

## Redis example

```python
import aioredis
```

---

# 🧯 Troubleshooting

### ❌ “Server disconnected”  
Fix: ensure claude_desktop_config.json has correct `cwd`.

### ❌ “No module named mcp_server”  
Fix:  
```
export PYTHONPATH="$PWD"
```

### ❌ asyncpg connection failure  
Check:
```
psql <connection-url>
```

---

# 🛡 Recommended .gitignore

```
venv/
.env
*.csv
*.log
__pycache__/
mcp_data/
```

---

# 🤝 Contributing

PRs welcome!  
Roadmap available on request.

---

# ⭐ Support

If you'd like:

- A web UI dashboard  
- Multi-target routing  
- Request logging  
- RBAC + auth tokens  
- Docker deployment  

I can generate it immediately.

---

# 🚀 Happy Hacking with MCP + Python + PostgreSQL!