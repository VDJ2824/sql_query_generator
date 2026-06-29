const mongoose = require("mongoose");
const {ROLES} = require("../constants/roles");

const databaseConnectionSchema = new mongoose.Schema(
  {
    connectionName: {
      type: String,
      required: true,
      trim: true,
    },
    databaseType: {
      type: String,
      enum: ["postgresql", "mysql", "sqlite", "POSTGRESQL", "MYSQL", "SQLITE"],
      required: true,
      lowercase: true,
    },
    dialect: {
      type: String,
      enum: ["postgres", "mysql", "sqlite"],
      required: true,
    },
    credentialEnvironmentVariableName: {
      type: String,
      required: true,
      trim: true,
    },
    allowedRoles: {
      type: [String],
      enum: Object.values(ROLES),
      default: [],
    },
    active: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: {createdAt: "createdAt", updatedAt: "updatedAt"},
    collection: "database_connections",
  },
);

module.exports = mongoose.model("DatabaseConnection", databaseConnectionSchema);
