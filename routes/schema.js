const router = require("express").Router();
const { getSchema, listTables } = require("../controllers/schemaController");

router.get("/get_schema", getSchema);
router.get("/list_tables", listTables);

module.exports = router;
