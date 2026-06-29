const mongoose = require("mongoose");

const auditLogSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      default: null,
      index: true,
    },
    action: {
      type: String,
      required: true,
    },
    databaseConnectionId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "DatabaseConnection",
      default: null,
    },
    generatedSql: {
      type: String,
      default: "",
    },
    finalEnforcedSql: {
      type: String,
      default: "",
    },
    status: {
      type: String,
      required: true,
    },
    message: {
      type: String,
      default: "",
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
  },
  {
    collection: "audit_logs",
  },
);

module.exports = mongoose.model("AuditLog", auditLogSchema);
