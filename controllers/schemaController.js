const pool = require("../config/db");

exports.getSchema = async (req, res) => {
  try {
    const sql = `
      SELECT table_name, column_name
      FROM information_schema.columns
      WHERE table_schema = 'public'
      ORDER BY table_name, ordinal_position;
    `;

    const result = await pool.query(sql);

    const schema = {};
    result.rows.forEach((row) => {
      if (!schema[row.table_name]) schema[row.table_name] = [];
      schema[row.table_name].push(row.column_name);
    });

    res.json({ ok: true, schema });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};

exports.listTables = async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT tablename FROM pg_catalog.pg_tables
      WHERE schemaname='public';
    `);

    res.json({ ok: true, tables: result.rows });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
};
