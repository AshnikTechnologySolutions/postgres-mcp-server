const pool = require("../config/db");

exports.tableStats = async (req, res) => {
  try {
    const sql = `
      SELECT
        relname AS table,
        n_live_tup AS rows,
        pg_total_relation_size(relid) AS total_size,
        pg_relation_size(relid) AS table_size,
        pg_indexes_size(relid) AS index_size,
        last_vacuum,
        last_autovacuum,
        last_analyze,
        last_autoanalyze
      FROM pg_stat_user_tables;
    `;
    const result = await pool.query(sql);

    res.json({ ok: true, stats: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};

exports.slowQueries = async (req, res) => {
  try {
    const sql = `
      SELECT query, calls, total_exec_time, mean_exec_time, rows
      FROM pg_stat_statements
      ORDER BY mean_exec_time DESC
      LIMIT 20;
    `;
    const result = await pool.query(sql);

    res.json({ ok: true, slow_queries: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};
