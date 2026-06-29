const express = require("express");
const crypto = require("crypto");
const AccessPolicy = require("../models/AccessPolicy");
const DatabaseConnection = require("../models/DatabaseConnection");
const GeneratedQueryOption = require("../models/GeneratedQueryOption");
const QueryHistory = require("../models/QueryHistory");
const SelectedQuery = require("../models/SelectedQuery");
const SqlIntelligenceClient = require("../services/SqlIntelligenceClient");
const asyncHandler = require("../middleware/asyncHandler");
const {authenticate} = require("../middleware/authMiddleware");
const {writeAuditLog} = require("../services/auditService");

const GENERATED_OPTION_TTL_MS = 15 * 60 * 1000;

const router = express.Router();

function safeConnection(connection) {
  return {
    connectionId: connection._id.toString(),
    databaseType: connection.databaseType,
    dialect: connection.dialect,
    credentialEnvironmentVariableName: connection.credentialEnvironmentVariableName,
  };
}

function verifiedUserContext(user) {
  return {
    userId: user._id.toString(),
    role: user.role,
    workspaceIdentifier: user.workspaceIdentifier,
    postgresWorkspaceName: user.postgresWorkspaceName,
    tidbWorkspaceName: user.tidbWorkspaceName,
  };
}

function workspaceForConnection(user, connection) {
  const databaseType = String(connection.databaseType || "").toLowerCase();
  if (databaseType === "mysql") {
    return user.tidbWorkspaceName || user.workspaceIdentifier;
  }
  if (databaseType === "postgresql" || databaseType === "postgres") {
    return user.postgresWorkspaceName || user.workspaceIdentifier;
  }
  return user.workspaceIdentifier;
}

function policyPayload(policy) {
  return {
    role: policy.role,
    databaseConnectionId: policy.databaseConnectionId.toString(),
    allowedOperations: policy.allowedOperations,
    allowedSchemas: policy.allowedSchemas,
    allowedTables: policy.allowedTables,
    blockedTables: policy.blockedTables,
    allowedColumns: policy.allowedColumns,
    requiresPreviewFor: policy.requiresPreviewFor,
    requiresConfirmationFor: policy.requiresConfirmationFor,
    active: policy.active,
  };
}

function safeQueryOption(option) {
  return {
    optionId: option.optionId,
    title: option.title,
    generatedSql: option.generatedSql,
    finalEnforcedSql: option.finalEnforcedSql,
    databaseType: option.optionPayload.databaseType || option.databaseType,
    sqlDialect: option.optionPayload.sqlDialect || option.dialect,
    queryType: option.queryType,
    tablesUsed: option.optionPayload.tablesUsed || [],
    columnsUsed: option.optionPayload.columnsUsed || [],
    explanation: option.optionPayload.explanation || "",
    riskLevel: option.optionPayload.riskLevel || "low",
    executionAllowed: Boolean(option.optionPayload.executionAllowed),
    requiresConfirmation: Boolean(option.optionPayload.requiresConfirmation),
    warnings: option.optionPayload.warnings || [],
    securityFilterExplanation: option.optionPayload.securityFilterExplanation || "",
  };
}

async function loadRequestContext(req, databaseConnectionId = null) {
  const connectionQuery = {
    active: true,
    allowedRoles: req.user.role,
  };
  if (databaseConnectionId) {
    connectionQuery._id = databaseConnectionId;
  }

  const connection = await DatabaseConnection.findOne(connectionQuery).sort({createdAt: -1});
  if (!connection) {
    const error = new Error("No active database connection is available for this user.");
    error.statusCode = 404;
    throw error;
  }

  const policies = await AccessPolicy.find({
    databaseConnectionId: connection._id,
    role: req.user.role,
    active: true,
  });

  return {
    connection,
    policies,
    sqlServicePayloadBase: {
      verifiedUser: verifiedUserContext(req.user),
      databaseConnection: safeConnection(connection),
      accessPolicies: policies.map(policyPayload),
    },
  };
}

function clientFor(req) {
  return req.app.locals.sqlIntelligenceClient || new SqlIntelligenceClient();
}

async function audit({req, action, connection, status, message, generatedSql = "", finalEnforcedSql = ""}) {
  await writeAuditLog({
    userId: req.user._id,
    action,
    databaseConnectionId: connection?._id || null,
    generatedSql,
    finalEnforcedSql,
    status,
    message,
  });
}

function canonicalTableName(tableName) {
  const normalized = String(tableName || "").toLowerCase();
  if (["employee", "employees"].includes(normalized)) return "Employee";
  if (["student", "students"].includes(normalized)) return "Students";
  if (["department", "departments"].includes(normalized)) return "Department";
  return tableName;
}

function selectFallbackTable(prompt, policies) {
  const promptLower = String(prompt || "").toLowerCase();
  const policyTables = [...new Set(
    policies.flatMap((policy) => policy.allowedTables || [])
      .filter(Boolean)
      .map(canonicalTableName),
  )];
  if (!policyTables.length) return "";

  const promptMatch = policyTables.find((table) => {
    const normalized = table.toLowerCase();
    const singular = normalized.endsWith("s") ? normalized.slice(0, -1) : normalized;
    return promptLower.includes(normalized) || promptLower.includes(singular);
  });
  return promptMatch || policyTables[0];
}

function fallbackColumnsForTable(tableName, policies) {
  const normalizedTable = String(tableName || "").toLowerCase();
  const columns = [...new Set(
    policies
      .filter((policy) => (policy.allowedTables || []).map((table) => table.toLowerCase()).includes(normalizedTable))
      .flatMap((policy) => policy.allowedColumns || [])
      .filter(Boolean),
  )];
  return columns;
}

function isDdlIntent(prompt) {
  const normalized = String(prompt || "").toLowerCase();
  return [
    /\bcreate\s+(?:a\s+)?table\b/,
    /\bcreate\s+table\b/,
    /\balter\s+table\b/,
    /\bdrop\s+table\b/,
    /\btruncate\s+table\b/,
    /\bcreate\s+index\b/,
    /\bdrop\s+index\b/,
  ].some((pattern) => pattern.test(normalized));
}

function isDatabaseAdminIntent(prompt) {
  const normalized = String(prompt || "").toLowerCase();
  return [
    /\bcreate\s+database\b/,
    /\bdrop\s+database\b/,
    /\bcreate\s+user\b/,
    /\bdrop\s+user\b/,
    /\bcreate\s+role\b/,
    /\bdrop\s+role\b/,
    /\balter\s+system\b/,
    /\bgrant\b/,
    /\brevoke\b/,
    /\buse\s+[a-zA-Z_][a-zA-Z0-9_]*\b/,
  ].some((pattern) => pattern.test(normalized));
}

function ddlAllowed(policies) {
  return policies.some((policy) => (policy.allowedOperations || []).map((operation) => operation.toUpperCase()).includes("DDL"));
}

function safeIdentifier(value) {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value || "");
}

function createTableSqlFromPrompt(prompt) {
  const tableMatch = String(prompt || "").match(/\bcreate\s+(?:a\s+)?table\s+(?:named\s+|called\s+)?([a-zA-Z_][a-zA-Z0-9_]*)/i);
  if (!tableMatch || !safeIdentifier(tableMatch[1])) return "";

  const columnsMatch = String(prompt || "").match(/\bcolumns?\s*:?\s*(.+)$/i);
  if (!columnsMatch) return "";
  const columns = [];
  for (const rawColumn of columnsMatch[1].split(/,|\band\b/i)) {
    const column = rawColumn.trim().replace(/[.;:]+$/g, "").split(/\s+/)[0];
    if (safeIdentifier(column) && !columns.includes(column)) {
      columns.push(column);
    }
  }
  if (!columns.length) return "";

  const definitions = columns.map((column) => (
    column.toLowerCase() === "id"
      ? `${column} INTEGER PRIMARY KEY`
      : ["roll_no", "email"].includes(column.toLowerCase())
        ? `${column} VARCHAR(${column.toLowerCase() === "roll_no" ? "50" : "255"}) NOT NULL UNIQUE`
        : `${column} VARCHAR(255) NOT NULL`
  ));
  return `CREATE TABLE ${tableMatch[1]} (${definitions.join(", ")})`;
}

function buildPolicyFallbackOptions({prompt, connection, policies, reason}) {
  if (isDatabaseAdminIntent(prompt)) {
    const warning = reason || "SQL intelligence service was unavailable, so Express returned a database administration safety explanation.";
    return [
      {
        optionId: 1,
        title: "Database administration is restricted",
        generatedSql: "",
        finalEnforcedSql: "",
        databaseType: connection.databaseType,
        sqlDialect: connection.dialect,
        queryType: "DDL",
        tablesUsed: [],
        columnsUsed: [],
        explanation: "CREATE DATABASE, DROP DATABASE, users, roles, grants, and system-level commands are blocked by policy.",
        riskLevel: "critical",
        executionAllowed: false,
        requiresConfirmation: false,
        warnings: [
          warning,
          "Database-level administration is restricted for security.",
          "Safe table-level DDL such as CREATE TABLE can still be previewed and executed after confirmation.",
        ],
      },
    ];
  }

  if (isDdlIntent(prompt)) {
    const warning = reason || "SQL intelligence service was unavailable, so Express returned a DDL safety explanation.";
    const generatedSql = ddlAllowed(policies) ? createTableSqlFromPrompt(prompt) : "";
    return [
      {
        optionId: 1,
        title: generatedSql ? "Create table from prompt" : "DDL request cannot be safely generated",
        generatedSql,
        finalEnforcedSql: generatedSql,
        databaseType: connection.databaseType,
        sqlDialect: connection.dialect,
        queryType: "DDL",
        tablesUsed: [],
        columnsUsed: [],
        explanation: generatedSql
          ? "Creates a new table using sanitized identifiers from the prompt. Requires preview and confirmation."
          : "The prompt asks to create or modify database structure, but the active policy or prompt format did not allow safe DDL generation.",
        riskLevel: "high",
        executionAllowed: Boolean(generatedSql),
        requiresConfirmation: Boolean(generatedSql),
        warnings: [
          warning,
          "No SELECT query was generated because the prompt is asking for DDL.",
          "Preview and execution still require Python SQL-service validation.",
        ],
      },
    ];
  }

  const tableName = selectFallbackTable(prompt, policies);
  const canSelect = policies.some((policy) => {
    const operations = (policy.allowedOperations || []).map((operation) => operation.toUpperCase());
    return operations.includes("DQL") || operations.includes("SELECT");
  });
  const warning = reason || "SQL intelligence service was unavailable, so Express returned conservative policy-based options.";

  if (!tableName || !canSelect) {
    return [
      {
        optionId: 1,
        title: "Generation unavailable",
        generatedSql: "",
        finalEnforcedSql: "",
        databaseType: connection.databaseType,
        sqlDialect: connection.dialect,
        queryType: "UNKNOWN",
        tablesUsed: [],
        columnsUsed: [],
        explanation: "No safe SELECT option could be generated from the active access policies.",
        riskLevel: "low",
        executionAllowed: false,
        requiresConfirmation: false,
        warnings: [warning],
      },
    ];
  }

  const allowedColumns = fallbackColumnsForTable(tableName, policies);
  const selectedColumns = allowedColumns.length ? allowedColumns.slice(0, 5).join(", ") : "*";
  const columnsUsed = allowedColumns.length ? allowedColumns.slice(0, 5) : [];

  return [
    {
      optionId: 1,
      title: `${tableName} records`,
      generatedSql: `SELECT ${selectedColumns} FROM ${tableName} LIMIT 20`,
      finalEnforcedSql: `SELECT ${selectedColumns} FROM ${tableName} LIMIT 20`,
      databaseType: connection.databaseType,
      sqlDialect: connection.dialect,
      queryType: "DQL",
      tablesUsed: [tableName],
      columnsUsed,
      explanation: "Conservative SELECT option generated from active MongoDB access policies.",
      riskLevel: "low",
      executionAllowed: true,
      requiresConfirmation: false,
      warnings: [warning, "Preview and execution still require Python SQL-service validation."],
    },
    {
      optionId: 2,
      title: `Count ${tableName} records`,
      generatedSql: `SELECT COUNT(*) AS total_records FROM ${tableName}`,
      finalEnforcedSql: `SELECT COUNT(*) AS total_records FROM ${tableName}`,
      databaseType: connection.databaseType,
      sqlDialect: connection.dialect,
      queryType: "DQL",
      tablesUsed: [tableName],
      columnsUsed: [],
      explanation: "Conservative aggregate option generated from active MongoDB access policies.",
      riskLevel: "low",
      executionAllowed: true,
      requiresConfirmation: false,
      warnings: [warning, "Preview and execution still require Python SQL-service validation."],
    },
  ];
}

function shouldUseGenerationFallback(error) {
  return !error.statusCode || error.statusCode >= 500;
}

function requiresConfirmedExecution(queryType) {
  return ["DML", "DDL", "INSERT", "UPDATE", "DELETE"].includes(String(queryType || "").toUpperCase());
}

function dropTableName(sql) {
  const match = String(sql || "").trim().match(/^DROP\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?$/i);
  return match ? match[1] : "";
}

function newConfirmationToken() {
  return crypto.randomBytes(24).toString("hex");
}

router.post(
  "/generate",
  authenticate,
  asyncHandler(async (req, res) => {
    const {prompt, databaseConnectionId} = req.body;
    if (!prompt || typeof prompt !== "string") {
      return res.status(400).json({message: "prompt is required."});
    }

    const {connection, policies, sqlServicePayloadBase} = await loadRequestContext(req, databaseConnectionId);
    let response;
    let generationStatus = "success";
    let generationMessage = "";
    try {
      response = await clientFor(req).generate({
        ...sqlServicePayloadBase,
        prompt,
      });
      generationMessage = `Generated ${(response.queryOptions || []).length} query option(s).`;
    } catch (error) {
      if (!shouldUseGenerationFallback(error)) {
        throw error;
      }
      generationStatus = "degraded";
      generationMessage = "Generated conservative fallback query options because the SQL intelligence service was unavailable.";
      response = {
        queryOptions: buildPolicyFallbackOptions({
          prompt,
          connection,
          policies,
          reason: error.message || "SQL intelligence service was unavailable.",
        }),
      };
    }

    await GeneratedQueryOption.deleteMany({userId: req.user._id});
    const expiresAt = new Date(Date.now() + GENERATED_OPTION_TTL_MS);
    const options = await GeneratedQueryOption.insertMany(
      (response.queryOptions || []).map((option, index) => ({
        userId: req.user._id,
        databaseConnectionId: connection._id,
        userPrompt: prompt,
        optionId: option.optionId || index + 1,
        title: option.title || "Generated query option",
        generatedSql: option.generatedSql || "",
        finalEnforcedSql: option.finalEnforcedSql || "",
        databaseType: connection.databaseType,
        dialect: connection.dialect,
        workspaceIdentifier: workspaceForConnection(req.user, connection),
        queryType: option.queryType || "UNKNOWN",
        optionPayload: option,
        expiresAt,
      })),
    );

    await audit({
      req,
      action: "QUERY_GENERATE",
      connection,
      status: generationStatus,
      message: generationMessage,
    });

    return res.json({queryOptions: options.map(safeQueryOption)});
  }),
);

router.post(
  "/select",
  authenticate,
  asyncHandler(async (req, res) => {
    const {optionId} = req.body;
    if (!optionId) {
      return res.status(400).json({message: "optionId is required."});
    }

    const generatedOption = await GeneratedQueryOption.findOne({
      userId: req.user._id,
      optionId,
      expiresAt: {$gt: new Date()},
    }).sort({createdAt: -1});
    if (!generatedOption) {
      return res.status(404).json({message: "Generated query option was not found or has expired."});
    }
    if (!generatedOption.generatedSql) {
      return res.status(400).json({message: "Selected option does not contain SQL that can be previewed or executed."});
    }

    const connection = await DatabaseConnection.findOne({
      _id: generatedOption.databaseConnectionId,
      active: true,
      allowedRoles: req.user.role,
    });
    if (!connection) {
      return res.status(404).json({message: "Selected query database connection is no longer available."});
    }

    await SelectedQuery.deleteMany({userId: req.user._id});
    const selectedQuery = await SelectedQuery.create({
      userId: req.user._id,
      databaseConnectionId: connection._id,
      optionId: generatedOption.optionId,
      title: generatedOption.title,
      generatedSql: generatedOption.generatedSql,
      finalEnforcedSql: generatedOption.finalEnforcedSql,
      databaseType: generatedOption.databaseType,
      dialect: generatedOption.dialect,
      workspaceIdentifier: generatedOption.workspaceIdentifier,
      userPrompt: generatedOption.userPrompt,
      queryType: generatedOption.queryType,
      expiresAt: new Date(Date.now() + GENERATED_OPTION_TTL_MS),
    });

    await audit({
      req,
      action: "QUERY_SELECT",
      connection,
      status: "selected",
      message: `Selected query option ${generatedOption.optionId}.`,
      generatedSql: generatedOption.generatedSql,
      finalEnforcedSql: generatedOption.finalEnforcedSql,
    });

    return res.status(201).json({
      selectedQuery: {
        id: selectedQuery._id.toString(),
        optionId: selectedQuery.optionId,
        title: selectedQuery.title,
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql,
        queryType: selectedQuery.queryType,
        expiresAt: selectedQuery.expiresAt,
      },
    });
  }),
);

async function loadSelectedQueryContext(req) {
  const selectedQuery = await SelectedQuery.findOne({
    userId: req.user._id,
    expiresAt: {$gt: new Date()},
  }).sort({createdAt: -1});
  if (!selectedQuery) {
    const error = new Error("No selected query is available. Select a generated option first.");
    error.statusCode = 404;
    throw error;
  }

  const context = await loadRequestContext(req, selectedQuery.databaseConnectionId);
  const expectedWorkspace = workspaceForConnection(req.user, context.connection);
  if (selectedQuery.workspaceIdentifier && selectedQuery.workspaceIdentifier !== expectedWorkspace) {
    const error = new Error("Selected query workspace does not match the authenticated user.");
    error.statusCode = 403;
    throw error;
  }
  return {selectedQuery, ...context};
}

router.post(
  "/preview",
  authenticate,
  asyncHandler(async (req, res) => {
    const {selectedQuery, connection, sqlServicePayloadBase} = await loadSelectedQueryContext(req);
    const response = await clientFor(req).preview({
      ...sqlServicePayloadBase,
      generatedSql: selectedQuery.generatedSql,
      selectedOptionId: selectedQuery.optionId,
    });
    selectedQuery.finalEnforcedSql = response.finalEnforcedSql || selectedQuery.finalEnforcedSql;
    selectedQuery.previewedAt = new Date();
    selectedQuery.lastPreviewStatus = response.executionAllowed ? "success" : "blocked";
    selectedQuery.confirmationToken = response.requiresConfirmation ? newConfirmationToken() : "";
    selectedQuery.requiredTypedConfirmation = response.requiredTypedConfirmation || dropTableName(selectedQuery.generatedSql);
    await selectedQuery.save();

    await audit({
      req,
      action: "QUERY_PREVIEW",
      connection,
      status: response.executionAllowed ? "success" : "blocked",
      message: response.impactMessage || "Preview completed.",
      generatedSql: response.generatedSql,
      finalEnforcedSql: response.finalEnforcedSql,
    });

    return res.json({
      ...response,
      confirmationToken: selectedQuery.confirmationToken || null,
      requiredTypedConfirmation: selectedQuery.requiredTypedConfirmation || response.requiredTypedConfirmation || null,
    });
  }),
);

router.post(
  "/execute",
  authenticate,
  asyncHandler(async (req, res) => {
    const {confirmed = false, confirmationToken = "", typedConfirmation = ""} = req.body;
    const {selectedQuery, connection, sqlServicePayloadBase} = await loadSelectedQueryContext(req);
    if (selectedQuery.executionStatus === "executed") {
      return res.status(409).json({
        success: false,
        message: "This selected query option has already been executed and cannot be executed again.",
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql || "",
        queryType: selectedQuery.queryType,
        rowsAffected: 0,
        resultRows: [],
        executionAllowed: false,
      });
    }
    if (requiresConfirmedExecution(selectedQuery.queryType) && !selectedQuery.previewedAt) {
      await audit({
        req,
        action: "QUERY_EXECUTE",
        connection,
        status: "blocked",
        message: `${selectedQuery.queryType} requires preview before execution.`,
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql,
      });
      await QueryHistory.create({
        userId: req.user._id,
        databaseConnectionId: connection._id,
        userPrompt: selectedQuery.userPrompt || "Selected query execution",
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql || "",
        queryType: selectedQuery.queryType,
        executionStatus: "blocked",
        rowsAffected: 0,
      });
      return res.status(409).json({
        success: false,
        message: `${selectedQuery.queryType} requires preview before execution.`,
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql || "",
        queryType: selectedQuery.queryType,
        rowsAffected: 0,
        resultRows: [],
        executionAllowed: false,
      });
    }
    if (requiresConfirmedExecution(selectedQuery.queryType)) {
      if (!confirmed || !selectedQuery.confirmationToken || confirmationToken !== selectedQuery.confirmationToken) {
        return res.status(409).json({
          success: false,
          message: `${selectedQuery.queryType} requires preview confirmation token before execution.`,
          generatedSql: selectedQuery.generatedSql,
          finalEnforcedSql: selectedQuery.finalEnforcedSql || "",
          queryType: selectedQuery.queryType,
          rowsAffected: 0,
          resultRows: [],
          executionAllowed: false,
        });
      }
    }
    const requiredDropTableName = dropTableName(selectedQuery.generatedSql);
    if (requiredDropTableName && typedConfirmation !== requiredDropTableName) {
      return res.status(409).json({
        success: false,
        message: `DROP TABLE requires typing the exact table name: ${requiredDropTableName}.`,
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql || "",
        queryType: selectedQuery.queryType,
        rowsAffected: 0,
        resultRows: [],
        executionAllowed: false,
      });
    }

    const executionLockId = crypto.randomUUID();
    const lockedQuery = await SelectedQuery.findOneAndUpdate(
      {
        _id: selectedQuery._id,
        executionStatus: {$ne: "executed"},
        $or: [{executionLockId: ""}, {executionLockId: {$exists: false}}],
      },
      {$set: {executionStatus: "executing", executionLockId}},
      {new: true},
    );
    if (!lockedQuery) {
      return res.status(409).json({
        success: false,
        message: "This selected query is already executing or has already been executed.",
        generatedSql: selectedQuery.generatedSql,
        finalEnforcedSql: selectedQuery.finalEnforcedSql || "",
        queryType: selectedQuery.queryType,
        rowsAffected: 0,
        resultRows: [],
        executionAllowed: false,
      });
    }

    let response;
    try {
      response = await clientFor(req).execute({
        ...sqlServicePayloadBase,
        generatedSql: selectedQuery.generatedSql,
        selectedOptionId: selectedQuery.optionId,
        confirmed,
        typedConfirmation,
      });
    } catch (error) {
      lockedQuery.executionStatus = "blocked";
      lockedQuery.executionLockId = "";
      await lockedQuery.save();
      throw error;
    }

    if (response.success) {
      lockedQuery.executionStatus = "executed";
      lockedQuery.executedAt = new Date();
      lockedQuery.executionLockId = "";
      await lockedQuery.save();
      await GeneratedQueryOption.updateOne(
        {
          userId: req.user._id,
          databaseConnectionId: connection._id,
          optionId: selectedQuery.optionId,
        },
        {$set: {executionStatus: "executed", executedAt: new Date()}},
      );
    } else {
      lockedQuery.executionStatus = "blocked";
      lockedQuery.executionLockId = "";
      await lockedQuery.save();
    }

    await QueryHistory.create({
      userId: req.user._id,
      databaseConnectionId: connection._id,
      userPrompt: selectedQuery.userPrompt || "Selected query execution",
      generatedSql: response.generatedSql || selectedQuery.generatedSql,
      finalEnforcedSql: response.finalEnforcedSql || "",
      queryType: response.queryType || selectedQuery.queryType,
      executionStatus: response.success ? "executed" : "blocked",
      rowsAffected: response.rowsAffected ?? null,
    });

    await audit({
      req,
      action: "QUERY_EXECUTE",
      connection,
      status: response.success ? "success" : "blocked",
      message: response.message || "Execution completed.",
      generatedSql: response.generatedSql,
      finalEnforcedSql: response.finalEnforcedSql,
    });

    return res.json(response);
  }),
);

router.use((error, req, res, next) => {
  if (error.statusCode) {
    return res.status(error.statusCode).json({message: error.message});
  }
  return next(error);
});

module.exports = router;
