require("../config/env");

const {connectDatabase, disconnectDatabase} = require("../config/database");
const AccessPolicy = require("../models/AccessPolicy");
const DatabaseConnection = require("../models/DatabaseConnection");
const User = require("../models/User");
const {ROLES} = require("../constants/roles");
const {hashPassword} = require("../utils/auth");
const {ensureUserWorkspaceMetadata} = require("../services/workspaceService");

const seedUsers = [
  {
    username: "admin",
    email: "admin@example.com",
    password: "admin123",
    role: ROLES.ADMIN,
  },
  {
    username: "demo_user",
    email: "demo.user@example.com",
    password: "user123",
    role: ROLES.USER,
  },
];

const demoConnections = [
  {
    connectionName: "Neon PostgreSQL Demo",
    databaseType: "postgresql",
    dialect: "postgres",
    credentialEnvironmentVariableName: "POSTGRES_DEMO_URL",
  },
  {
    connectionName: "TiDB Cloud MySQL-Compatible Demo",
    databaseType: "mysql",
    dialect: "mysql",
    credentialEnvironmentVariableName: "MYSQL_DEMO_URL",
  },
];

const blockedInternalTables = [
  "users",
  "audit_logs",
  "query_history",
  "selected_queries",
  "generated_query_options",
  "database_connections",
  "access_policies",
  "information_schema",
  "pg_catalog",
  "mysql",
  "sys",
  "performance_schema",
];

async function upsertUsers() {
  for (const user of seedUsers) {
    const passwordHash = await hashPassword(user.password);
    await User.updateOne(
      {username: user.username},
      {
        $set: {
          email: user.email,
          passwordHash,
          role: user.role,
          active: true,
        },
      },
      {upsert: true},
    );
    const savedUser = await User.findOne({username: user.username});
    await ensureUserWorkspaceMetadata(savedUser);
  }
}

async function upsertPoliciesForConnection(connection) {
  const policies = [
    {
      role: ROLES.USER,
      allowedOperations: ["DQL", "DML", "DDL"],
      allowedSchemas: [],
      allowedTables: [],
      blockedTables: blockedInternalTables,
      allowedColumns: [],
      requiresPreviewFor: ["INSERT", "UPDATE", "DELETE", "DDL"],
      requiresConfirmationFor: ["INSERT", "UPDATE", "DELETE", "DDL"],
    },
    {
      role: ROLES.ADMIN,
      allowedOperations: ["DQL", "DML", "DDL"],
      allowedSchemas: [],
      allowedTables: [],
      blockedTables: blockedInternalTables,
      allowedColumns: [],
      requiresPreviewFor: ["INSERT", "UPDATE", "DELETE", "DDL"],
      requiresConfirmationFor: ["INSERT", "UPDATE", "DELETE", "DDL"],
    },
  ];

  for (const policy of policies) {
    await AccessPolicy.updateOne(
      {
        role: policy.role,
        databaseConnectionId: connection._id,
      },
      {
        $set: {
          ...policy,
          databaseConnectionId: connection._id,
          active: true,
        },
      },
      {upsert: true},
    );
  }
}

async function seedConnectionAndPolicies() {
  await DatabaseConnection.updateMany(
    {
      $or: [
        {credentialEnvironmentVariableName: "SQLITE_DEMO_PATH"},
        {databaseType: "sqlite"},
      ],
    },
    {$set: {active: false}},
  );

  for (const metadata of demoConnections) {
    const connection = await DatabaseConnection.findOneAndUpdate(
      {credentialEnvironmentVariableName: metadata.credentialEnvironmentVariableName},
      {
        ...metadata,
        allowedRoles: [ROLES.USER, ROLES.ADMIN],
        active: true,
      },
      {upsert: true, new: true},
    );
    await upsertPoliciesForConnection(connection);
  }
}

async function main() {
  await connectDatabase();
  await upsertUsers();
  await seedConnectionAndPolicies();
  await disconnectDatabase();
  console.log("Seed users, demo connections, and access policies created.");
}

main().catch(async (error) => {
  console.error(error);
  await disconnectDatabase();
  process.exit(1);
});
