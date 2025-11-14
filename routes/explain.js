const router = require("express").Router();
const { explainQuery } = require("../controllers/explainController");

router.post("/explain_query", explainQuery);

module.exports = router;
