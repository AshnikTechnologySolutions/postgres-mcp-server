import axios from "axios";
import dotenv from "dotenv";
dotenv.config();

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const MCP = process.env.MCP_SERVER_URL;
const MODEL = process.env.MODEL || "gpt-4-turbo-preview";

async function askDB(question) {
  console.log("\n🤖  Question:", question);

  // Step 1: Ask the LLM to translate question → SQL
  const aiResponse = await axios.post(
    "https://api.openai.com/v1/chat/completions",
    {
      model: MODEL,
      messages: [
        {
          role: "system",
          content:
            "You are a PostgreSQL expert. The database has one table named customers with columns: id, name, country, revenue. Only generate SQL queries for that table.",
        },
        { role: "user", content: question },
      ],
      temperature: 0,
    },
    { headers: { Authorization: `Bearer ${OPENAI_API_KEY}` } }
  );

  // Clean GPT output: remove markdown fences like ```sql ... ```
  let sql = aiResponse.data.choices[0].message.content.trim();
  sql = sql.replace(/```sql/gi, "").replace(/```/g, "").trim();
  console.log("🧠  Generated SQL:\n", sql);

  // Step 2: Send SQL to MCP Server
  try {
    const result = await axios.post(`${MCP}/sql_query`, { query: sql });
    console.log("📊  Query result:");
    console.table(result.data.rows);
  } catch (err) {
    console.error("❌  MCP Server error:", err.response?.data || err.message);
  }
}

// Run interactively from CLI
const question = process.argv.slice(2).join(" ");
if (!question) {
  console.log("Usage: node index.js \"Show top 3 customers by revenue\"");
  process.exit(1);
}
askDB(question);
