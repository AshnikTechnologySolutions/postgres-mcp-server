// controllers/healthController.js - Upgraded Health Endpoint
const pool = require("../config/db");

exports.healthCheck = async (req, res) => {
  try {
    const uptimeQuery = `
      SELECT 
        now() - pg_postmaster_start_time() AS uptime,
        pg_postmaster_start_time() AS started_at,
        version() AS postgres_version,
        current_database() AS database_name;
    `;

    const connectionsQuery = `
      SELECT COUNT(*) AS active_connections
      FROM pg_stat_activity
      WHERE datname = current_database();
    `;

    const uptimeResult = await pool.query(uptimeQuery);
    const connectionResult = await pool.query(connectionsQuery);

    res.json({
      ok: true,
      service: "PostgreSQL MCP Server",
      status: "running",
      uptime: uptimeResult.rows[0].uptime,
      started_at: uptimeResult.rows[0].started_at,
      postgres_version: uptimeResult.rows[0].postgres_version,
      database: uptimeResult.rows[0].database_name,
      active_connections: connectionResult.rows[0].active_connections
    });
  } catch (err) {
    res.status(500).json({
      ok: false,
      error: "Unable to fetch health status",
      details: err.message,
    });
  }
};