import axios from "axios";
import dotenv from "dotenv";
import readline from "readline";
import fs from "fs";
dotenv.config();

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const MCP = process.env.MCP_SERVER_URL;
const MODEL = process.env.MODEL || "gpt-4-turbo-preview";
const LOG_FILE = "chat_history.json";

// Initialize history with schema context
const chatHistory = [
  {
  role: "system",
  content: `
You are a PostgreSQL expert. Generate ONLY SQL (no text, no markdown).
The PostgreSQL database schema is:

customers(id, name, email, country, created_at)
categories(id, name)
products(id, name, price, category_id)
orders(id, customer_id, order_date, status, total_amount)
order_items(id, order_id, order_date, product_id, quantity, price)
payments(id, order_id, paid_at, amount, method)
shipments(id, order_id, shipped_at, carrier, tracking_number)
inventory(id, product_id, warehouse, quantity, updated_at)

Rules:
- Use column names exactly as defined above.
- Join tables correctly via foreign keys:
    orders.customer_id → customers.id
    order_items.order_id → orders.id
    order_items.product_id → products.id
    payments.order_id → orders.id
    shipments.order_id → orders.id
    inventory.product_id → products.id
- Never reference columns that do not exist.
- Always output only pure SQL.
`,
},
];

// Helper function to append logs to JSON file
function logInteraction(entry) {
  let existingLogs = [];
  if (fs.existsSync(LOG_FILE)) {
    try {
      existingLogs = JSON.parse(fs.readFileSync(LOG_FILE, "utf-8"));
    } catch {
      existingLogs = [];
    }
  }
  existingLogs.push(entry);
  fs.writeFileSync(LOG_FILE, JSON.stringify(existingLogs, null, 2));
}

async function askDB(question) {
  chatHistory.push({ role: "user", content: question });
  const timestamp = new Date().toISOString();

  try {
    // Step 1: Ask GPT to create SQL
    const aiResponse = await axios.post(
      "https://api.openai.com/v1/chat/completions",
      {
        model: MODEL,
        messages: chatHistory,
        temperature: 0,
      },
      { headers: { Authorization: `Bearer ${OPENAI_API_KEY}` } }
    );

    // Clean GPT output
    let sql = aiResponse.data.choices[0].message.content.trim();
    sql = sql.replace(/```sql/gi, "").replace(/```/g, "").trim();

    console.log("\n🧠  Generated SQL:\n", sql);

    // Step 2: Send to MCP Server
    const result = await axios.post(`${MCP}/sql_query`, { query: sql });
    const rows = result.data.rows;
    console.log("📊  Query result:");
    console.table(rows);

    // Save to chat log
    logInteraction({ timestamp, question, sql, rows });

    chatHistory.push({ role: "assistant", content: sql });
  } catch (err) {
    const errorMsg = err.response?.data?.error || err.message;
    console.error("❌  Error:", errorMsg);
    logInteraction({ timestamp, question, error: errorMsg });
  }
}

// CLI loop
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

console.log("🤖 PostgreSQL Chatbot Connected! (type 'exit' to quit)\n");

function promptUser() {
  rl.question("🧩 Ask your DB > ", async (question) => {
    if (question.toLowerCase() === "exit") {
      console.log("👋 Goodbye!");
      rl.close();
      process.exit(0);
    }
    await askDB(question);
    promptUser();
  });
}

promptUser();