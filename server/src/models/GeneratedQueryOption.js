const mongoose = require("mongoose");

const generatedQueryOptionSchema = new mongoose.Schema(
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
      index: true,
    },
    userPrompt: {
      type: String,
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
      default: "",
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
    queryType: {
      type: String,
      required: true,
    },
    optionPayload: {
      type: Object,
      default: {},
    },
    executionStatus: {
      type: String,
      enum: ["pending", "executed"],
      default: "pending",
      index: true,
    },
    executedAt: {
      type: Date,
      default: null,
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
    collection: "generated_query_options",
  },
);

generatedQueryOptionSchema.index({userId: 1, optionId: 1, createdAt: -1});

module.exports = mongoose.model("GeneratedQueryOption", generatedQueryOptionSchema);
