const express = require("express");

const healthRoutes = require("./routes/health");
const schemaRoutes = require("./routes/schema");
const queryRoutes = require("./routes/query");
const explainRoutes = require("./routes/explain");
const statsRoutes = require("./routes/stats");

const app = express();
app.use(express.json());

// Mount all routes
app.use("/", healthRoutes);
app.use("/", schemaRoutes);
app.use("/", queryRoutes);
app.use("/", explainRoutes);
app.use("/", statsRoutes);

module.exports = app;
