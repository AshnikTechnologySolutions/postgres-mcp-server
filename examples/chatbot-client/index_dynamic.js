// index_dynamic.js - Upgraded Intelligent Chatbot with Tool Routing
import axios from "axios";
import dotenv from "dotenv";
import readline from "readline";

dotenv.config();

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const MCP_SERVER_URL = process.env.MCP_SERVER_URL || "http://localhost:8000";

// -------------------------------------------------------------
// Load database schema dynamically from MCP Server
// -------------------------------------------------------------
async function loadSchema() {
  const res = await axios.get(`${MCP_SERVER_URL}/get_schema`);
  const schema = res.data.schema;

  let schemaText = "";
  for (const [table, columns] of Object.entries(schema)) {
    schemaText += `${table}(${columns.join(", ")})\n`;
  }
  return schemaText;
}

// -------------------------------------------------------------
// Intent Detection Layer (Tool Router)
// -------------------------------------------------------------
function detectIntent(question) {
  const q = question.toLowerCase().trim();

  // Uptime intent (higher priority than generic health)
  if (q.includes("how long") || q.includes("uptime") || q.includes("from how long") || q.includes("up since") || q.includes("started") || q.includes("start time")) {
    return "uptime";
  }

  if (q.includes("health") || q.includes("running") || q.includes("alive") || q.includes("status")) {
    return "health";
  }

  if (q.includes("table stats") || q.includes("stats")) {
    return "table_stats";
  }

  if (q.includes("slow queries") || q.includes("slowest") || q.includes("top slow")) {
    return "slow_queries";
  }

  if (q.startsWith("explain")) {
    return "explain";
  }

  if (q.startsWith("safe:")) {
    return "safe_query";
  }

  return "sql"; // default path
}

// -------------------------------------------------------------
// Tool Execution Functions
// -------------------------------------------------------------
async function runHealth() {
  const res = await axios.get(`${MCP_SERVER_URL}/`);
  return res.data;
}

async function runTableStats() {
  const res = await axios.get(`${MCP_SERVER_URL}/stats/table_stats`);
  return res.data;
}

async function runSlowQueries() {
  const res = await axios.get(`${MCP_SERVER_URL}/stats/slow_queries`);
  return res.data;
}

// Uptime helper: returns result of uptime SQL
async function runUptime() {
  // Use the server-side SQL to compute uptime
  const sql = "SELECT now() - pg_postmaster_start_time() AS uptime;";
  const res = await runSQL(sql);
  return res;
}

async function runExplain(rawQuestion, schemaText) {
  // Extract SQL after the word "explain"
  const sql = rawQuestion.replace(/explain/i, "").trim();

  const payload = {
    query: sql,
    analyze: false,
  };

  const res = await axios.post(`${MCP_SERVER_URL}/explain_query`, payload);
  return res.data;
}

async function runSafeSQL(question) {
  const sql = question.replace(/^safe:/i, "").trim();

  const res = await axios.post(`${MCP_SERVER_URL}/sql_safe_query`, { query: sql });
  return res.data;
}

// -------------------------------------------------------------
// OpenAI SQL Generator (using Responses API)
// -------------------------------------------------------------
async function askGPT_forSQL(question, schemaText) {
  const systemPrompt = `
You are a PostgreSQL SQL generator.

Important rules:
- Only generate pure SQL (no markdown, no backticks).
- The database uses partitioned tables, but ALWAYS query parent tables only.
- NEVER reference partition names like orders_2023_01.
- ONLY use these tables:
  orders, order_items, customers, products, categories, payments, shipments, inventory.
- SQL must be perfectly valid PostgreSQL syntax.

Schema:
${schemaText}
`;

  const payload = {
    model: "gpt-4.1-mini",
    input: [
      { role: "system", content: systemPrompt },
      { role: "user", content: question }
    ]
  };

  const response = await axios.post(
    "https://api.openai.com/v1/responses",
    payload,
    {
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      }
    }
  );

  return response.data.output[0].content[0].text.trim();
}

async function runSQL(sql) {
  const res = await axios.post(`${MCP_SERVER_URL}/sql_query`, { query: sql });
  return res.data;
}

// -------------------------------------------------------------
// MAIN Chat Loop with Intelligent Routing
// -------------------------------------------------------------
async function main() {
  console.log("🔄 Loading schema from MCP server...");
  const schemaText = await loadSchema();
  console.log("✔ Schema loaded dynamically!\n");

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  async function ask() {
    rl.question("🧩 Ask your DB > ", async (question) => {
      // Ignore empty input
      if (!question.trim()) {
        console.log("⏭  Ignored empty input.");
        return ask();
      }
      if (question === "exit") {
        rl.close();
        return;
      }

      const intent = detectIntent(question);

      try {
        // -------------------------------
        // Tool Routing
        // -------------------------------
        if (intent === "uptime") {
          const res = await runUptime();

          function intervalToString(intervalObj) {
            if (!intervalObj) return "unknown";

            const parts = [];
            if (intervalObj.years) parts.push(`${intervalObj.years} years`);
            if (intervalObj.months) parts.push(`${intervalObj.months} months`);
            if (intervalObj.days) parts.push(`${intervalObj.days} days`);
            if (intervalObj.hours) parts.push(`${intervalObj.hours} hours`);
            if (intervalObj.minutes) parts.push(`${intervalObj.minutes} minutes`);
            if (intervalObj.seconds) parts.push(`${Math.floor(intervalObj.seconds)} seconds`);

            return parts.join(" ");
          }

          console.log("\n⏳ Database Uptime:\n");
          console.log(intervalToString(res.rows[0].uptime), "\n");

          return ask();
        }

        if (intent === "health") {
          const res = await runHealth();
          console.log("\n❤️ DB Health Status:\n", res, "\n");
          return ask();
        }

        if (intent === "table_stats") {
          const res = await runTableStats();
          console.log("\n📊 Table Stats:\n");
          console.table(res.stats);
          return ask();
        }

        if (intent === "slow_queries") {
          const res = await runSlowQueries();
          console.log("\n🐢 Slow Queries:\n");
          console.table(res.slow_queries);
          return ask();
        }

        if (intent === "explain") {
          const res = await runExplain(question, schemaText);
          console.log("\n📈 Explain Plan:\n");
          console.log(res.plan.join("\n"));
          return ask();
        }

        if (intent === "safe_query") {
          const res = await runSafeSQL(question);
          console.log("\n🛡 Safe SQL Result:\n");
          console.table(res.rows);
          return ask();
        }

        // -------------------------------
        // Default flow → AI SQL Generator
        // -------------------------------
        const sql = await askGPT_forSQL(question, schemaText);
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
