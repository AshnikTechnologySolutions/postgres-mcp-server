const pool = require("../config/db");

exports.explainQuery = async (req, res) => {
  const { query, analyze = false } = req.body;

  if (!query)
    return res.status(400).json({ ok: false, error: "Missing query" });

  try {
    const exe = analyze
      ? `EXPLAIN ANALYZE ${query}`
      : `EXPLAIN ${query}`;

    const result = await pool.query(exe);

    res.json({
      ok: true,
      plan: result.rows.map(r => r["QUERY PLAN"]),
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};
