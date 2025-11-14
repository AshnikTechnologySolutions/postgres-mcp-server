const router = require("express").Router();
const { sqlQuery, safeQuery } = require("../controllers/queryController");

router.post("/sql_query", sqlQuery);
router.post("/sql_safe_query", safeQuery);

module.exports = router;
