# 🧩 PostgreSQL MCP Server  
### by [Ashnik Technology Solutions](https://github.com/AshnikTechnologySolutions)

A lightweight **Model Context Protocol (MCP)** server that allows AI models or agents (such as Claude, ChatGPT, or custom LLM clients) to securely connect to PostgreSQL and run queries in a controlled way.

---

## 🚀 Features
- ✅ **MCP-compatible** JSON/HTTP interface  
- ✅ Tools: `list_tables`, `sql_query` (with optional safe query control)  
- ✅ **Secure via environment variables** – no hardcoded credentials  
- ✅ Easily extendable to add custom AI-accessible tools  
- ✅ Works with Claude Desktop or any LLM supporting MCP servers  
- ✅ CI/CD workflow for PostgreSQL testing via GitHub Actions  

---

## 🧰 Tech Stack
- **Node.js 18+**
- **Express.js**
- **PostgreSQL 13+**
- **dotenv** for configuration management  

---

## ⚙️ Prerequisites
Before you start, make sure you have:
- PostgreSQL installed and running (`brew install postgresql`)
- Node.js ≥ 18 installed
- A test database created (`mcp_demo`)
- A dedicated DB user (`mcpuser`) with read-only access  

---

## 🪄 Quick Start

```bash
# Clone the repo
git clone https://github.com/AshnikTechnologySolutions/postgres-mcp-server.git

# Move into directory
cd postgres-mcp-server

# Install dependencies
npm install

# Copy and configure your environment file
cp .env.example .env

# Start the MCP server
npm start