const pool = require("../config/db");

exports.sqlQuery = async (req, res) => {
  const { query } = req.body;

  if (!query)
    return res.status(400).json({ ok: false, error: "Missing query in body" });

  try {
    const result = await pool.query(query);
    res.json({ ok: true, rows: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};

// Read-only SQL firewall
exports.safeQuery = async (req, res) => {
  const { query } = req.body;

  const forbidden = /(insert|update|delete|drop|alter|truncate)/i;

  if (forbidden.test(query)) {
    return res.status(403).json({
      ok: false,
      error: "Read-only mode: write operations are not allowed",
    });
  }

  try {
    const result = await pool.query(query);
    res.json({ ok: true, rows: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};
