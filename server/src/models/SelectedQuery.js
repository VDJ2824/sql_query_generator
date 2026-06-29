const mongoose = require("mongoose");

const selectedQuerySchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      index: true,
    },
    databaseConnectionId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "DatabaseConnection",
      required: true,
    },
    optionId: {
      type: Number,
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
    generatedSql: {
      type: String,
      required: true,
    },
    finalEnforcedSql: {
      type: String,
      default: "",
    },
    databaseType: {
      type: String,
      default: "",
    },
    dialect: {
      type: String,
      default: "",
    },
    workspaceIdentifier: {
      type: String,
      default: "",
    },
    userPrompt: {
      type: String,
      default: "",
    },
    queryType: {
      type: String,
      required: true,
    },
    previewedAt: {
      type: Date,
      default: null,
    },
    lastPreviewStatus: {
      type: String,
      default: "",
    },
    confirmationToken: {
      type: String,
      default: "",
    },
    requiredTypedConfirmation: {
      type: String,
      default: "",
    },
    executionStatus: {
      type: String,
      enum: ["pending", "executing", "executed", "blocked"],
      default: "pending",
      index: true,
    },
    executedAt: {
      type: Date,
      default: null,
    },
    executionLockId: {
      type: String,
      default: "",
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
    expiresAt: {
      type: Date,
      required: true,
      index: {expires: 0},
    },
  },
  {
    collection: "selected_queries",
  },
);

module.exports = mongoose.model("SelectedQuery", selectedQuerySchema);
