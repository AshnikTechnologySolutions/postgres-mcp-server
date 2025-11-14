const router = require("express").Router();
const { tableStats, slowQueries } = require("../controllers/statsController");

router.get("/stats/table_stats", tableStats);
router.get("/stats/slow_queries", slowQueries);

module.exports = router;
