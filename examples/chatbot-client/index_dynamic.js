// index_dynamic.js - Chatbot client with dynamic schema loading
import axios from "axios";
import dotenv from "dotenv";
import readline from "readline";
dotenv.config();

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const MCP_SERVER_URL = process.env.MCP_SERVER_URL || "http://localhost:8000";

async function loadSchema() {
  const res = await axios.get(`${MCP_SERVER_URL}/get_schema`);
  const schema = res.data.schema;
  let schemaText = "";
  for (const [table, columns] of Object.entries(schema)) {
    schemaText += `${table}(${columns.join(", ")})\n`;
  }
  return schemaText;
}

async function askGPT(question, schemaText) {
  const prompt = `
You are a PostgreSQL SQL generator.

Important rules:
- The database uses partitioned tables (orders, order_items), but you must ALWAYS query the parent table only.
- NEVER reference individual partition tables like orders_2023_01 or order_items_2024_05.
- ALWAYS use: orders, order_items, products, customers, payments, shipments, inventory.
- PostgreSQL automatically scans all partitions.

The database schema is:
${schemaText}

Generate ONLY pure SQL. No markdown, no explanations.
`;

  const response = await axios.post(
    "https://api.openai.com/v1/chat/completions",
    {
      model: "gpt-4.1-mini",
      messages: [
        { role: "system", content: prompt },
        { role: "user", content: question },
      ],
    },
    {
      headers: { Authorization: `Bearer ${OPENAI_API_KEY}` },
    }
  );

  return response.data.choices[0].message.content.trim();
}

async function runSQL(sql) {
  const res = await axios.post(`${MCP_SERVER_URL}/sql_query`, { query: sql });
  return res.data;
}

async function main() {
  console.log("🔄 Loading schema from MCP server...");
  const schemaText = await loadSchema();
  console.log("✔ Schema loaded dynamically!\n");

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  async function ask() {
    rl.question("🧩 Ask your DB > ", async (question) => {
      if (question === "exit") {
        rl.close();
        return;
      }

      try {
        const sql = await askGPT(question, schemaText);
        console.log(`\n🧠 Generated SQL:\n${sql}\n`);

        const result = await runSQL(sql);
        console.log("📊 Result:\n");
console.table(result.rows);
      } catch (err) {
        console.log("❌ Error:", err.message);
      }

      ask();
    });
  }

  ask();
}

main();
