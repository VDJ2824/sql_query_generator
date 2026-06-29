const express = require("express");
const AccessPolicy = require("../models/AccessPolicy");
const DatabaseConnection = require("../models/DatabaseConnection");
const asyncHandler = require("../middleware/asyncHandler");
const {authenticate} = require("../middleware/authMiddleware");
const {requireRoles} = require("../middleware/roleMiddleware");
const {ROLES} = require("../constants/roles");
const {writeAuditLog} = require("../services/auditService");
const SqlIntelligenceClient = require("../services/SqlIntelligenceClient");

const router = express.Router();

function publicConnection(connection) {
  return {
    id: connection._id.toString(),
    connectionName: connection.connectionName,
    databaseType: connection.databaseType,
    dialect: connection.dialect,
    allowedRoles: connection.allowedRoles,
    active: connection.active,
    createdAt: connection.createdAt,
  };
}

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

function clientFor(req) {
  return req.app.locals.sqlIntelligenceClient || new SqlIntelligenceClient();
}

router.get(
  "/",
  authenticate,
  asyncHandler(async (req, res) => {
    const connections = await DatabaseConnection.find({
      active: true,
      allowedRoles: req.user.role,
    }).sort({createdAt: -1});
    return res.json({databaseConnections: connections.map(publicConnection)});
  }),
);

router.get(
  "/:id/tables",
  authenticate,
  asyncHandler(async (req, res) => {
    const connection = await DatabaseConnection.findOne({
      _id: req.params.id,
      active: true,
      allowedRoles: req.user.role,
    });
    if (!connection) {
      return res.status(404).json({message: "Database connection was not found or is not available for your role."});
    }

    const policies = await AccessPolicy.find({
      databaseConnectionId: connection._id,
      role: req.user.role,
      active: true,
    });

    const schema = await clientFor(req).schema({
      verifiedUser: verifiedUserContext(req.user),
      databaseConnection: safeConnection(connection),
      accessPolicies: policies.map(policyPayload),
    });
    const tables = (schema.allowedTables || [])
      .map((table) => table.tableName || table.table_name)
      .filter(Boolean)
      .sort((left, right) => left.localeCompare(right));

    return res.json({
      databaseConnectionId: connection._id.toString(),
      databaseType: connection.databaseType,
      dialect: connection.dialect,
      tables,
    });
  }),
);

router.post(
  "/",
  authenticate,
  requireRoles(ROLES.ADMIN),
  asyncHandler(async (req, res) => {
    const {connectionName, databaseType, dialect, credentialEnvironmentVariableName, allowedRoles, active} = req.body;
    if (!connectionName || !databaseType || !credentialEnvironmentVariableName) {
      return res.status(400).json({
        message: "connectionName, databaseType, and credentialEnvironmentVariableName are required.",
      });
    }
    if (!/^[A-Z_][A-Z0-9_]*$/i.test(credentialEnvironmentVariableName)) {
      return res.status(400).json({
        message: "credentialEnvironmentVariableName must be an environment variable name, not a connection string.",
      });
    }

    const normalizedDatabaseType = String(databaseType).toLowerCase();
    const resolvedDialect = dialect || {postgresql: "postgres", mysql: "mysql", sqlite: "sqlite"}[normalizedDatabaseType];
    if (!resolvedDialect) {
      return res.status(400).json({message: "Unsupported databaseType."});
    }

    const connection = await DatabaseConnection.create({
      connectionName,
      databaseType: normalizedDatabaseType,
      dialect: resolvedDialect,
      credentialEnvironmentVariableName,
      allowedRoles: allowedRoles || [ROLES.ADMIN],
      active: active ?? true,
    });

    await writeAuditLog({
      userId: req.user._id,
      action: "DATABASE_CONNECTION_CREATE",
      databaseConnectionId: connection._id,
      status: "success",
      message: `Created database connection metadata ${connection.connectionName}`,
    });

    return res.status(201).json({databaseConnection: publicConnection(connection)});
  }),
);

router.post(
  "/:id/select",
  authenticate,
  asyncHandler(async (req, res) => {
    await writeAuditLog({
      userId: req.user._id,
      action: "QUERY_SELECT",
      status: "blocked",
      message: "Deprecated selection route blocked. Use POST /api/queries/select with optionId only.",
    });
    return res.status(410).json({
      message: "This route is deprecated. Select generated queries through POST /api/queries/select using optionId only.",
    });
  }),
);

module.exports = router;
