const mongoose = require("mongoose");
const {ROLES} = require("../constants/roles");

const accessPolicySchema = new mongoose.Schema(
  {
    role: {
      type: String,
      enum: Object.values(ROLES),
      required: true,
    },
    databaseConnectionId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "DatabaseConnection",
      required: true,
    },
    allowedOperations: {
      type: [String],
      enum: ["DQL", "DML", "DDL", "SELECT", "INSERT", "UPDATE", "DELETE"],
      default: ["DQL"],
    },
    allowedSchemas: {
      type: [String],
      default: [],
    },
    allowedTables: {
      type: [String],
      default: [],
    },
    blockedTables: {
      type: [String],
      default: [],
    },
    allowedColumns: {
      type: [String],
      default: [],
    },
    requiresPreviewFor: {
      type: [String],
      enum: ["INSERT", "UPDATE", "DELETE", "DDL"],
      default: ["INSERT", "UPDATE", "DELETE"],
    },
    requiresConfirmationFor: {
      type: [String],
      enum: ["INSERT", "UPDATE", "DELETE", "DDL"],
      default: ["INSERT", "UPDATE", "DELETE"],
    },
    active: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: true,
    collection: "access_policies",
  },
);

module.exports = mongoose.model("AccessPolicy", accessPolicySchema);
