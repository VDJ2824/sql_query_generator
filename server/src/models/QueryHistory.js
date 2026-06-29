const mongoose = require("mongoose");

const queryHistorySchema = new mongoose.Schema(
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
    userPrompt: {
      type: String,
      required: true,
    },
    generatedSql: {
      type: String,
      default: "",
    },
    finalEnforcedSql: {
      type: String,
      default: "",
    },
    queryType: {
      type: String,
      required: true,
    },
    executionStatus: {
      type: String,
      required: true,
    },
    rowsAffected: {
      type: Number,
      default: null,
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
  },
  {
    collection: "query_history",
  },
);

module.exports = mongoose.model("QueryHistory", queryHistorySchema);
