# 🚀 AI-Enhanced PostgreSQL MCP Server
![Architecture](./assets/architecture.png)

This repository provides a complete **Model Context Protocol (MCP) Server for PostgreSQL**, an **AI-powered SQL Chatbot**, and tools to generate and load a **20GB+ e-commerce dataset** for analytics and natural-language-to-SQL workloads.

It is designed for:
- AI-driven SQL query generation
- Large-scale dataset testing (20GB+)
- Benchmarking PostgreSQL performance
- Demonstrating MCP integration with LLMs
- Real-world e-commerce analytics scenarios

---

## 📌 Features

### 🧠 AI Chatbot for PostgreSQL
- Understands natural-language questions
- Generates SQL dynamically using **OpenAI GPT models**
- Loads schema dynamically from MCP Server
- Supports complex analytical queries
- Human-readable table output

### 🗄 PostgreSQL MCP Server
- Implements REST-like MCP interface
- `/list_tables`, `/get_schema`, `/sql_query`
- Connects securely via environment variables
- Works with any PostgreSQL cluster

### 📦 Massive 20GB+ Synthetic Dataset
- E-commerce schema:
  - customers, orders, order_items
  - products, categories, payments, shipments
  - inventory
- Partitioned monthly tables for orders & items
- High-volume COPY-based ingestion
- Perfect for benchmarking and AI demos

### 🛠 Tools Included
- `generate_20gb.py` → generate CSV dataset (20GB+)
- `create_partitions.py` → auto-create monthly partitions
- `import_all.sh` → bulk import + ANALYZE
- `schema_20gb.sql` → production-grade e-commerce schema
- `README_DATA_LOAD.md` → full end-to-end data guide

---

## 📂 Repository Structure
```
postgres-mcp-server/
├── index.js                     # MCP Server
├── package.json
├── tools/
│   ├── schema_20gb.sql         # E-commerce schema
│   ├── create_partitions.py    # Monthly partitions
│   ├── generate_20gb.py        # 20GB data generator
│   ├── import_all.sh           # Bulk import script
│   └── README_DATA_LOAD.md     # Data loading guide
├── examples/
│   └── chatbot-client/
│       ├── index_dynamic.js    # AI chatbot (dynamic schema)
│       ├── single-query.js
│       ├── package.json
└── README.md
```

---

## ⚙️ Installation & Setup

### 1️⃣ Install Dependencies
```bash
npm install
```

### Configure PostgreSQL connection:
```bash
export DATABASE_URL=postgres://user:password@localhost:5432/mcp_demo
```

### Start MCP Server:
```bash
npm start
```
You should see:
```
🚀 MCP Server for PostgreSQL running on port 8000
```

---

## 💬 Run the AI Chatbot

Navigate to chatbot directory:
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

Ask questions like:
```
Top 10 products by revenue
Monthly revenue trend
Which carrier delivered the most orders?
Revenue by country
```

---

## 📦 Generate the 20GB Dataset

Full guide located at:
```
tools/README_DATA_LOAD.md
```

Quick start:
```bash
pip3 install faker python-dateutil
python3 tools/generate_20gb.py --out /tmp/mcp_data
```

Create partitions:
```bash
python3 tools/create_partitions.py
```

Import all data:
```bash
bash tools/import_all.sh /tmp/mcp_data
```

---

## 🎯 Example AI-Generated Queries

### Top 10 customers by spending
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

### Most used shipping carrier
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
PRs are welcome! Suggested areas:
- Better dataset generators
- Benchmark & load-testing scripts
- UI dashboards
- More MCP integrations

---

## ⭐ Support
For issues or feature requests, please open a GitHub issue.

🚀 Happy hacking with PostgreSQL + MCP + AI!
