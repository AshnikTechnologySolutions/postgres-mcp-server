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

## 📥 Clone the Repository
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server.git
cd postgres-mcp-server

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

## 📂 Repository Structure

```
postgres-mcp-server/
├── app.js                         # Main MCP Server (Express)
├── index.js                       # Legacy entry (may be unused)
├── config/
│   └── db.js                      # PostgreSQL pool
├── controllers/                   # Server controllers
│   ├── healthController.js
│   ├── queryController.js
│   ├── schemaController.js
│   ├── explainController.js
│   └── statsController.js
├── routes/                        # API routes
│   ├── health.js
│   ├── query.js
│   ├── schema.js
│   ├── explain.js
│   └── stats.js
├── examples/
│   └── chatbot-client/            # AI Chatbot
│       ├── index_dynamic.js
│       ├── index.js
│       ├── single-query.js
│       ├── chat_history.json
│       ├── package.json
│       └── package-lock.json
├── utility/                       # Data generation & tools
│   ├── generate_20gb.py
│   ├── create_partitions.py
│   ├── import_all.sh
│   └── schema_20gb.sql
├── assets/
│   └── architecture.png
├── README.md
├── package.json
└── package-lock.json
```

---

## ⚙️ Installation & Setup

### 1️⃣ Install dependencies
```bash
npm install
```

### 2️⃣ Configure PostgreSQL connection
```bash
export DATABASE_URL=postgres://user:password@localhost:5432/mcp_demo
```

### 3️⃣ Start MCP Server
```bash
npm start
```
You should see:
```
🚀 MCP Server for PostgreSQL running on port 8000
```

---

## 💬 Start the AI Chatbot

```bash
cd examples/chatbot-client
npm install
node index_dynamic.js
```

Output:
```
🔄 Loading schema from MCP server...
✔ Schema loaded dynamically!
```

Ask anything:

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
