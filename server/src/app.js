require("./config/env");

const cors = require("cors");
const express = require("express");
const helmet = require("helmet");

const authRoutes = require("./routes/authRoutes");
const auditRoutes = require("./routes/auditRoutes");
const databaseConnectionRoutes = require("./routes/databaseConnectionRoutes");
const historyRoutes = require("./routes/historyRoutes");
const queryRoutes = require("./routes/queryRoutes");
const {getDatabaseConnectionState, isDatabaseConnected} = require("./config/database");

const DEFAULT_CLIENT_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"];

function allowedClientOrigins() {
  return (process.env.CLIENT_URL || process.env.CLIENT_ORIGIN || DEFAULT_CLIENT_ORIGINS.join(","))
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
}

function createApp() {
  const app = express();

  app.use(helmet());
  app.use(cors({origin: allowedClientOrigins()}));
  app.use(express.json({limit: "1mb"}));

  app.get("/api/health", (req, res) => {
    res.json({
      status: "ok",
      service: "server",
      database: {
        connected: isDatabaseConnected(),
        state: getDatabaseConnectionState(),
      },
      responsibilities: ["auth", "users", "policies", "selected_queries", "history", "audit_logs"],
    });
  });

  app.use("/api/auth", authRoutes);
  app.use("/api/database-connections", databaseConnectionRoutes);
  app.use("/api/queries", queryRoutes);
  app.use("/api/history", historyRoutes);
  app.use("/api/admin", auditRoutes);

  app.use((req, res) => {
    res.status(404).json({message: "Route not found."});
  });

  app.use((error, req, res, next) => {
    console.error(error);
    res.status(500).json({message: "Internal server error."});
  });

  return app;
}

module.exports = createApp;
