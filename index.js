// index.js
const express = require("express");
const { Pool } = require("pg");
require("dotenv").config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const app = express();
app.use(express.json());

// Health check
app.get("/", (req, res) => {
  res.json({ ok: true, service: "PostgreSQL MCP Server", status: "running" });
});

// Get database schema (tables + columns)
app.get("/get_schema", async (req, res) => {
  try {
    const query = `
      SELECT table_name, column_name
      FROM information_schema.columns
      WHERE table_schema = 'public'
      ORDER BY table_name, ordinal_position;
    `;

    const result = await pool.query(query);

    const schema = {};
    result.rows.forEach((row) => {
      if (!schema[row.table_name]) schema[row.table_name] = [];
      schema[row.table_name].push(row.column_name);
    });

    res.json({ ok: true, schema });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

// List tables
app.get("/list_tables", async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public'"
    );
    res.json({ ok: true, tables: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

// SQL query (for demo)
app.post("/sql_query", async (req, res) => {
  const { query } = req.body;
  if (!query)
    return res.status(400).json({ ok: false, error: "Missing query in body" });

  try {
    const result = await pool.query(query);
    res.json({ ok: true, rows: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

const port = process.env.PORT || 8000;
app.listen(port, () =>
  console.log(`🚀 MCP Server for PostgreSQL running on port ${port}`)
);