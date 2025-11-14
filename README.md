# 🚀 AI-Enhanced PostgreSQL MCP Server
![Architecture](./assets/architecture.png)

This repository provides a complete **Model Context Protocol (MCP) Server for PostgreSQL**, an **AI-powered SQL Chatbot**, upgraded **health monitoring**, and tools to generate and load a **20GB+ e-commerce dataset**.

It is designed for:
- AI-driven SQL query generation  
- Large-scale dataset testing (20GB+)  
- Benchmarking PostgreSQL performance  
- Demonstrating MCP integration with LLMs  
- Real-world e-commerce analytics  
- Intelligent DB insights (uptime, stats, explain plans, safe queries)



---

## 📌 Features

### 🧠 AI Chatbot for PostgreSQL (Dynamic & Intelligent)
- Understands natural-language questions  
- Uses **OpenAI GPT (Responses API)**  
- Auto-loads schema dynamically from MCP Server  
- Built-in **Intent Router**:
  - `uptime`
  - `health`
  - `table stats`
  - `slow queries`
  - `explain`
  - `safe query`
  - SQL generation (default)
- Auto schema refresh (every 5 minutes)
- Command history  
- Pretty table output  

### 🗄 PostgreSQL MCP Server  
- REST-like MCP interface  
- Endpoints:
  - `GET /` → Enhanced health (uptime, version, connections)  
  - `GET /list_tables`  
  - `GET /get_schema`  
  - `POST /sql_query`  
  - `POST /sql_safe_query`  
  - `POST /explain_query`  
  - `GET /stats/table_stats`  
  - `GET /stats/slow_queries`  
- Secure via environment variables  
- Works with any PostgreSQL cluster  

### 📦 20GB+ Synthetic E-Commerce Dataset  
- Tables:
  - customers, orders, order_items  
  - products, categories  
  - payments, shipments  
  - inventory  
- Monthly partitioned tables  
- COPY-based high-speed ingestion  
- Ideal for AI + analytics  

### 🛠 Included Tools  
- `generate_20gb.py` → dataset generator  
- `create_partitions.py` → creates monthly partitions  
- `import_all.sh` → bulk loader  
- `schema_20gb.sql` → complete schema  
- `README_DATA_LOAD.md` → full data loading guide  

---

# 🏗️ Installation Guide (PostgreSQL + MCP Server + AI Chatbot)

This setup supports both **local** and **3-VM distributed deployments**.

---

## 🖥️ 1. Install PostgreSQL (Database Server)

Ubuntu / Debian:
```
sudo apt update
sudo apt install postgresql postgresql-contrib
```

CentOS / RHEL:
```
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
```

Create user + database:
```
sudo -u postgres psql
CREATE ROLE mcpuser WITH LOGIN PASSWORD 'mcppassword';
CREATE DATABASE mcp_demo OWNER mcpuser;
GRANT ALL PRIVILEGES ON DATABASE mcp_demo TO mcpuser;
\q
```

Optional: Allow remote MCP server:
```
host  mcp_demo  mcpuser  <MCP_SERVER_IP>/32  md5
```

Restart PostgreSQL:
```
sudo systemctl restart postgresql
```

---

## 🖥️ 2. Install MCP Server (Node.js + Express)

Install Node.js:
```
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs git
```

Clone & install:
```
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server.git
cd postgres-mcp-server
npm install
```

Create `.env`:
```
cp .env.example .env
```

Add:
```
DATABASE_URL=postgres://mcpuser:mcppassword@<POSTGRES_IP>:5432/mcp_demo
PORT=8000
```

Start server:
```
npm start
```

You should see:
```
🚀 MCP Server for PostgreSQL running on port 8000
```

---

## 🖥️ 3. Install AI Chatbot Client

```
cd examples/chatbot-client
npm install
```

Create `.env`:
```
OPENAI_API_KEY=your-api-key-here
MCP_SERVER_URL=http://<MCP_SERVER_IP>:8000
```

Run chatbot:
```
node index_dynamic.js
```
Expected output:
```
🔄 Loading schema from MCP server...
✔ Schema loaded dynamically!

🧩 Ask your DB >
```

---

## 🌐 4. Distributed Deployment (3 VMs)

| Component | VM | Purpose |
|----------|----|----------|
| PostgreSQL | VM-3 | Stores data |
| MCP Server | VM-2 | API bridge |
| AI Chatbot | VM-1 | NL → SQL |

Firewall rules:

PostgreSQL:
```
sudo ufw allow from <VM2_IP> to any port 5432
```

MCP Server:
```
sudo ufw allow from <VM1_IP> to any port 8000
```

---

## ✔ Validation

Test MCP → PostgreSQL:
```
psql -h <POSTGRES_IP> -U mcpuser -d mcp_demo -c "SELECT 1"
```

Test Chatbot → MCP:
```
curl http://<MCP_IP>:8000/
```


## 💬 Ask Questions Using the Chatbot

```
Top 10 products by revenue
Monthly revenue trend
Show table stats
Explain select * from customers
How long has my DB been running?
Is my DB running?
Slow queries
safe: select * from products
```

---

## 🩺 Enhanced Health Endpoint

```json
{
  "ok": true,
  "service": "PostgreSQL MCP Server",
  "status": "running",
  "uptime": "12 days 4 hours 31 minutes",
  "started_at": "2025-01-20 12:11:03",
  "postgres_version": "PostgreSQL 15.6 ...",
  "database": "mcp_demo",
  "active_connections": 18
}
```

---

## 📦 Generate the 20GB Dataset

Full guide:  
`utility/README_DATA_LOAD.md`

Quick steps:

```bash
python3 utility/generate_20gb.py --out /tmp/mcp_data
python3 utility/create_partitions.py
bash utility/import_all.sh /tmp/mcp_data
```

---

## 🎯 Example AI-Generated Queries

### Top spenders
```sql
SELECT c.name, SUM(o.total_amount) AS total_spending
FROM customers c
JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name
ORDER BY total_spending DESC
LIMIT 10;
```

### Monthly revenue
```sql
SELECT date_trunc('month', order_date) AS month,
       SUM(total_amount)
FROM orders
GROUP BY month
ORDER BY month;
```

### Popular shipping carriers
```sql
SELECT carrier, COUNT(*)
FROM shipments
GROUP BY carrier
ORDER BY COUNT(*) DESC;
```

---

## 🛡 Recommended .gitignore

```
node_modules/
.env
*.csv
mcp_data/
*.log
.DS_Store
examples/chatbot-client/chat_history.json
__pycache__/
```

---

## 🤝 Contributing

PRs welcome! Areas to contribute:
- More dataset generators  
- Dashboards / UI  
- New MCP tools  
- Query performance helpers  

---

## ⭐ Support

For issues or feature requests, open a GitHub issue.

🚀 Happy hacking with **PostgreSQL + MCP + AI**!
