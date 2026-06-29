const request = require("supertest");
const User = require("../src/models/User");
const AccessPolicy = require("../src/models/AccessPolicy");
const AuditLog = require("../src/models/AuditLog");
const DatabaseConnection = require("../src/models/DatabaseConnection");
const GeneratedQueryOption = require("../src/models/GeneratedQueryOption");
const QueryHistory = require("../src/models/QueryHistory");
const SelectedQuery = require("../src/models/SelectedQuery");
const {ROLES} = require("../src/constants/roles");
const {hashPassword} = require("../src/utils/auth");
const {clearDatabase, startTestApp, stopTestApp} = require("./helpers/testServer");

let app;
let sqlClient;

beforeAll(async () => {
  app = await startTestApp();
});

afterAll(async () => {
  await stopTestApp();
});

beforeEach(async () => {
  await clearDatabase();
  sqlClient = {
    generate: jest.fn(),
    preview: jest.fn(),
    execute: jest.fn(),
  };
  app.locals.sqlIntelligenceClient = sqlClient;
});

async function createUser(overrides = {}) {
  return User.create({
    username: "user",
    email: "user@example.com",
    passwordHash: await hashPassword("Password123"),
    role: ROLES.USER,
    active: true,
    ...overrides,
  });
}

async function login(username = "user") {
  const email = `${username}@example.com`;
  const challenge = await request(app)
    .post("/api/auth/login")
    .send({email, password: "Password123"});
  const response = await request(app)
    .post("/api/auth/verify-login-otp")
    .send({email, otp: challenge.body.debugOtp});
  return response.body.accessToken;
}

async function createConnectionAndPolicy(userRole = ROLES.USER, overrides = {}) {
  const connection = await DatabaseConnection.create({
    connectionName: "Reporting SQLite",
    databaseType: "sqlite",
    dialect: "sqlite",
    credentialEnvironmentVariableName: "SQLITE_REPORTING_URL",
    allowedRoles: [userRole],
    active: true,
  });
  await AccessPolicy.create({
    role: userRole,
    databaseConnectionId: connection._id,
    allowedOperations: overrides.allowedOperations || ["SELECT"],
    allowedTables: overrides.allowedTables || ["sales"],
    blockedTables: ["users", "audit_logs", "query_history", "selected_queries"],
    allowedColumns: overrides.allowedColumns || ["id", "region", "amount"],
    requiresPreviewFor: ["INSERT", "UPDATE", "DELETE", "DDL"],
    requiresConfirmationFor: ["INSERT", "UPDATE", "DELETE", "DDL"],
    active: true,
  });
  return connection;
}

test("generate builds trusted USER context from MongoDB and stores options server-side", async () => {
  await createUser();
  const connection = await createConnectionAndPolicy();
  sqlClient.generate.mockResolvedValue({
    queryOptions: [
      {
        optionId: 1,
        title: "Sales by region",
        generatedSql: "SELECT region, amount FROM sales",
        finalEnforcedSql: "SELECT region, amount FROM sales",
        databaseType: "SQLITE",
        sqlDialect: "sqlite",
        queryType: "SELECT",
        tablesUsed: ["sales"],
        columnsUsed: ["region", "amount"],
        explanation: "Shows allowed sales columns.",
        riskLevel: "low",
        executionAllowed: true,
        requiresConfirmation: false,
        warnings: [],
        securityFilterExplanation: "No identity-based row-level restriction is configured.",
      },
    ],
  });

  const response = await request(app)
    .post("/api/queries/generate")
    .set("Authorization", `Bearer ${await login()}`)
    .send({
      prompt: "show sales",
      databaseConnectionId: connection._id.toString(),
      role: ROLES.ADMIN,
      userId: "forged-user-id",
      workspaceIdentifier: "user_attacker_ffffff",
      postgresWorkspaceName: "user_attacker_ffffff",
      tidbWorkspaceName: "user_attacker_ffffff",
      department: "Finance",
      employeeId: 999,
      accessPolicies: [{allowedTables: ["users"]}],
    });

  expect(response.status).toBe(200);
  expect(response.body.queryOptions).toHaveLength(1);
  const payload = sqlClient.generate.mock.calls[0][0];
  expect(payload.verifiedUser.userId).toEqual(expect.any(String));
  expect(payload.verifiedUser.userId).not.toBe("forged-user-id");
  expect(payload.verifiedUser.role).toBe(ROLES.USER);
  expect(payload.verifiedUser.workspaceIdentifier).toMatch(/^user_user_[a-f0-9]{6}$/);
  expect(payload.verifiedUser.workspaceIdentifier).not.toBe("user_attacker_ffffff");
  expect(payload.verifiedUser.postgresWorkspaceName).toBe(payload.verifiedUser.workspaceIdentifier);
  expect(payload.verifiedUser.tidbWorkspaceName).toBe(payload.verifiedUser.workspaceIdentifier);
  expect(payload.verifiedUser.department).toBeUndefined();
  expect(payload.verifiedUser.employeeId).toBeUndefined();
  expect(payload.databaseConnection.credentialEnvironmentVariableName).toBe("SQLITE_REPORTING_URL");
  expect(payload.databaseConnection.databaseType).toBe("sqlite");
  expect(payload.databaseConnection.dialect).toBe("sqlite");
  expect(payload.accessPolicies[0].allowedTables).toEqual(["sales"]);
  expect(payload.accessPolicies[0].blockedTables).toContain("users");

  const storedOptions = await GeneratedQueryOption.find({});
  expect(storedOptions).toHaveLength(1);
  expect(storedOptions[0].userPrompt).toBe("show sales");
  expect(storedOptions[0].workspaceIdentifier).toBe(payload.verifiedUser.workspaceIdentifier);
  expect(storedOptions[0].databaseType).toBe("sqlite");
  expect(storedOptions[0].dialect).toBe("sqlite");
  expect(await AuditLog.countDocuments({action: "QUERY_GENERATE"})).toBe(1);
});

test("generate returns conservative fallback options when SQL service is unavailable", async () => {
  await createUser();
  const connection = await createConnectionAndPolicy(ROLES.USER, {
    allowedOperations: ["DQL"],
    allowedTables: ["employee"],
    allowedColumns: ["employee_id", "name", "salary"],
  });
  const error = new Error("Selected target database is not reachable or credentials are invalid.");
  error.statusCode = 503;
  sqlClient.generate.mockRejectedValue(error);

  const response = await request(app)
    .post("/api/queries/generate")
    .set("Authorization", `Bearer ${await login()}`)
    .send({
      prompt: "show employees",
      databaseConnectionId: connection._id.toString(),
    });

  expect(response.status).toBe(200);
  expect(response.body.queryOptions).toHaveLength(2);
  expect(response.body.queryOptions[0].generatedSql).toBe("SELECT employee_id, name, salary FROM Employee LIMIT 20");
  expect(response.body.queryOptions[0].warnings.join(" ")).toMatch(/Preview and execution still require Python SQL-service validation/);
  const storedOptions = await GeneratedQueryOption.find({userId: (await User.findOne({username: "user"}))._id}).sort({optionId: 1});
  expect(storedOptions).toHaveLength(2);
  expect(storedOptions[0].queryType).toBe("DQL");
  const auditLog = await AuditLog.findOne({action: "QUERY_GENERATE"});
  expect(auditLog.status).toBe("degraded");
});

test("generate fallback creates DDL option instead of selecting existing tables", async () => {
  await createUser();
  const connection = await createConnectionAndPolicy(ROLES.USER, {
    allowedOperations: ["DQL", "DDL"],
    allowedTables: ["students"],
    allowedColumns: ["student_id", "name", "email"],
  });
  const error = new Error("SQL intelligence service is not configured.");
  error.statusCode = 503;
  sqlClient.generate.mockRejectedValue(error);

  const response = await request(app)
    .post("/api/queries/generate")
    .set("Authorization", `Bearer ${await login()}`)
    .send({
      prompt: "create table named Student with columns: id, name, roll_no and email.",
      databaseConnectionId: connection._id.toString(),
    });

  expect(response.status).toBe(200);
  expect(response.body.queryOptions).toHaveLength(1);
  expect(response.body.queryOptions[0].queryType).toBe("DDL");
  expect(response.body.queryOptions[0].executionAllowed).toBe(true);
  expect(response.body.queryOptions[0].requiresConfirmation).toBe(true);
  expect(response.body.queryOptions[0].generatedSql).toBe(
    "CREATE TABLE Student (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, roll_no VARCHAR(50) NOT NULL UNIQUE, email VARCHAR(255) NOT NULL UNIQUE)",
  );
  expect(response.body.queryOptions[0].warnings.join(" ")).toMatch(/No SELECT query was generated/);
});

test("generate fallback blocks database administration DDL instead of treating it like table DDL", async () => {
  await createUser();
  const connection = await createConnectionAndPolicy(ROLES.USER, {
    allowedOperations: ["DQL", "DDL"],
    allowedTables: ["students"],
    allowedColumns: ["student_id", "name", "email"],
  });
  const error = new Error("SQL intelligence service is not configured.");
  error.statusCode = 503;
  sqlClient.generate.mockRejectedValue(error);

  const response = await request(app)
    .post("/api/queries/generate")
    .set("Authorization", `Bearer ${await login()}`)
    .send({
      prompt: "create database college_demo",
      databaseConnectionId: connection._id.toString(),
    });

  expect(response.status).toBe(200);
  expect(response.body.queryOptions).toHaveLength(1);
  expect(response.body.queryOptions[0].queryType).toBe("DDL");
  expect(response.body.queryOptions[0].generatedSql).toBe("");
  expect(response.body.queryOptions[0].executionAllowed).toBe(false);
  expect(response.body.queryOptions[0].requiresConfirmation).toBe(false);
  expect(response.body.queryOptions[0].warnings.join(" ")).toMatch(/Database-level administration is restricted/);
});

test("select uses stored generated option and ignores arbitrary frontend SQL", async () => {
  const user = await createUser();
  const connection = await createConnectionAndPolicy();
  await GeneratedQueryOption.create({
    userId: user._id,
    databaseConnectionId: connection._id,
    userPrompt: "show sales",
    optionId: 1,
    title: "Safe option",
    generatedSql: "SELECT region FROM sales",
    finalEnforcedSql: "SELECT region FROM sales",
    queryType: "SELECT",
    optionPayload: {executionAllowed: true},
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });

  const response = await request(app)
    .post("/api/queries/select")
    .set("Authorization", `Bearer ${await login()}`)
    .send({
      optionId: 1,
      generatedSql: "DROP TABLE sales",
      queryType: "DDL",
    });

  expect(response.status).toBe(201);
  const selected = await SelectedQuery.findOne({userId: user._id});
  expect(selected.generatedSql).toBe("SELECT region FROM sales");
  expect(selected.finalEnforcedSql).toBe("SELECT region FROM sales");
  expect(selected.queryType).toBe("SELECT");
});

test("another user cannot select an option they do not own", async () => {
  const owner = await createUser();
  await createUser({username: "intruder", email: "intruder@example.com"});
  const connection = await createConnectionAndPolicy();
  await GeneratedQueryOption.create({
    userId: owner._id,
    databaseConnectionId: connection._id,
    userPrompt: "show sales",
    optionId: 1,
    title: "Owner option",
    generatedSql: "SELECT region FROM sales",
    queryType: "SELECT",
    optionPayload: {executionAllowed: true},
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });

  const response = await request(app)
    .post("/api/queries/select")
    .set("Authorization", `Bearer ${await login("intruder")}`)
    .send({optionId: 1});

  expect(response.status).toBe(404);
  expect(await SelectedQuery.countDocuments({userId: owner._id})).toBe(0);
});

test("preview retrieves selected SQL server-side before calling Python service", async () => {
  const user = await createUser();
  const connection = await createConnectionAndPolicy();
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: connection._id,
    optionId: 1,
    title: "Safe option",
    generatedSql: "SELECT region FROM sales",
    queryType: "SELECT",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });
  sqlClient.preview.mockResolvedValue({
    generatedSql: "SELECT region FROM sales",
    finalEnforcedSql: "SELECT region FROM sales",
    previewSql: "SELECT * FROM preview_source LIMIT 20",
    queryType: "SELECT",
    estimatedRows: 1,
    previewRows: [{region: "West"}],
    impactMessage: "SELECT preview is limited to 20 rows.",
    riskLevel: "low",
    executionAllowed: true,
    requiresConfirmation: false,
    warnings: [],
  });

  const response = await request(app)
    .post("/api/queries/preview")
    .set("Authorization", `Bearer ${await login()}`)
    .send({generatedSql: "DROP TABLE sales"});

  expect(response.status).toBe(200);
  expect(sqlClient.preview.mock.calls[0][0].generatedSql).toBe("SELECT region FROM sales");
  expect(sqlClient.preview.mock.calls[0][0].generatedSql).not.toBe("DROP TABLE sales");
  const selectedAfterPreview = await SelectedQuery.findOne({userId: user._id});
  expect(selectedAfterPreview.previewedAt).toBeTruthy();
  expect(await AuditLog.countDocuments({action: "QUERY_PREVIEW"})).toBe(1);
});

test("execute sends selected SQL and confirmation to Python service and saves history", async () => {
  const user = await createUser();
  const connection = await createConnectionAndPolicy();
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: connection._id,
    optionId: 1,
    title: "Safe option",
    generatedSql: "SELECT region FROM sales",
    userPrompt: "show sales",
    queryType: "SELECT",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });
  sqlClient.execute.mockResolvedValue({
    success: true,
    message: "SELECT executed successfully.",
    generatedSql: "SELECT region FROM sales",
    finalEnforcedSql: "SELECT region FROM sales",
    queryType: "SELECT",
    rowsAffected: 1,
    resultRows: [{region: "West"}],
    executionAllowed: true,
  });

  const response = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({confirmed: true, generatedSql: "DROP TABLE sales"});

  expect(response.status).toBe(200);
  expect(sqlClient.execute.mock.calls[0][0].generatedSql).toBe("SELECT region FROM sales");
  expect(sqlClient.execute.mock.calls[0][0].confirmed).toBe(true);
  expect(await QueryHistory.countDocuments({userId: user._id, executionStatus: "executed"})).toBe(1);
  expect(await AuditLog.countDocuments({action: "QUERY_EXECUTE"})).toBe(1);
});

test("execute blocks write queries until the selected query has been previewed", async () => {
  const user = await createUser();
  const connection = await createConnectionAndPolicy(ROLES.USER, {allowedOperations: ["SELECT", "UPDATE"]});
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: connection._id,
    optionId: 1,
    title: "Update sales",
    generatedSql: "UPDATE sales SET amount = amount + 1 WHERE id = 1",
    finalEnforcedSql: "UPDATE sales SET amount = amount + 1 WHERE id = 1",
    userPrompt: "update sales",
    queryType: "UPDATE",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });

  const response = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({confirmed: true});

  expect(response.status).toBe(409);
  expect(response.body.success).toBe(false);
  expect(sqlClient.execute).not.toHaveBeenCalled();
  expect(await QueryHistory.countDocuments({userId: user._id, executionStatus: "blocked"})).toBe(1);
});

test("execute allows confirmed write after preview and stores successful attempt", async () => {
  const user = await createUser();
  const connection = await createConnectionAndPolicy(ROLES.USER, {allowedOperations: ["SELECT", "UPDATE"]});
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: connection._id,
    optionId: 1,
    title: "Update sales",
    generatedSql: "UPDATE sales SET amount = amount + 1 WHERE id = 1",
    finalEnforcedSql: "UPDATE sales SET amount = amount + 1 WHERE id = 1",
    userPrompt: "update sales",
    queryType: "UPDATE",
    previewedAt: new Date(),
    lastPreviewStatus: "success",
    confirmationToken: "preview-token",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });
  sqlClient.execute.mockResolvedValue({
    success: true,
    message: "UPDATE executed successfully.",
    generatedSql: "UPDATE sales SET amount = amount + 1 WHERE id = 1",
    finalEnforcedSql: "UPDATE sales SET amount = amount + 1 WHERE id = 1",
    queryType: "UPDATE",
    rowsAffected: 1,
    resultRows: [],
    executionAllowed: true,
  });

  const response = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({confirmed: true, confirmationToken: "preview-token"});

  expect(response.status).toBe(200);
  expect(sqlClient.execute).toHaveBeenCalledTimes(1);
  expect(sqlClient.execute.mock.calls[0][0].confirmed).toBe(true);
  expect(await QueryHistory.countDocuments({userId: user._id, executionStatus: "executed"})).toBe(1);
});

test("drop table requires exact typed confirmation and cannot execute twice", async () => {
  const user = await createUser();
  const connection = await createConnectionAndPolicy(ROLES.USER, {allowedOperations: ["DDL"]});
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: connection._id,
    optionId: 1,
    title: "Drop table",
    generatedSql: "DROP TABLE Student",
    finalEnforcedSql: "DROP TABLE Student",
    userPrompt: "drop table Student",
    queryType: "DDL",
    previewedAt: new Date(),
    lastPreviewStatus: "success",
    confirmationToken: "drop-token",
    requiredTypedConfirmation: "Student",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });
  sqlClient.execute.mockResolvedValue({
    success: true,
    message: "DDL executed successfully.",
    generatedSql: "DROP TABLE Student",
    finalEnforcedSql: "DROP TABLE Student",
    queryType: "DDL",
    rowsAffected: 0,
    resultRows: [],
    executionAllowed: true,
  });

  const wrongTyped = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({confirmed: true, confirmationToken: "drop-token", typedConfirmation: "student"});
  const first = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({confirmed: true, confirmationToken: "drop-token", typedConfirmation: "Student"});
  const second = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({confirmed: true, confirmationToken: "drop-token", typedConfirmation: "Student"});

  expect(wrongTyped.status).toBe(409);
  expect(first.status).toBe(200);
  expect(second.status).toBe(409);
  expect(sqlClient.execute).toHaveBeenCalledTimes(1);
});

test("selected PostgreSQL option cannot be executed against a MySQL request body override", async () => {
  const user = await createUser();
  const postgresConnection = await DatabaseConnection.create({
    connectionName: "PostgreSQL Demo",
    databaseType: "postgresql",
    dialect: "postgres",
    credentialEnvironmentVariableName: "POSTGRES_DEMO_URL",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  const mysqlConnection = await DatabaseConnection.create({
    connectionName: "MySQL Demo",
    databaseType: "mysql",
    dialect: "mysql",
    credentialEnvironmentVariableName: "MYSQL_DEMO_URL",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  const sqliteConnection = await DatabaseConnection.create({
    connectionName: "SQLite Demo",
    databaseType: "sqlite",
    dialect: "sqlite",
    credentialEnvironmentVariableName: "SQLITE_DEMO_PATH",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  await AccessPolicy.create({
    role: ROLES.USER,
    databaseConnectionId: postgresConnection._id,
    allowedOperations: ["SELECT"],
    allowedTables: ["employee"],
    blockedTables: [],
    allowedColumns: [],
    active: true,
  });
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: postgresConnection._id,
    optionId: 1,
    title: "PostgreSQL employees",
    generatedSql: "SELECT employee_id, name FROM employee",
    queryType: "SELECT",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });
  sqlClient.execute.mockResolvedValue({
    success: true,
    message: "SELECT executed successfully.",
    generatedSql: "SELECT employee_id, name FROM employee",
    finalEnforcedSql: "SELECT employee_id, name FROM employee",
    queryType: "SELECT",
    rowsAffected: 0,
    resultRows: [],
    executionAllowed: true,
  });

  const response = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({databaseConnectionId: mysqlConnection._id.toString(), confirmed: false});

  expect(response.status).toBe(200);
  const payload = sqlClient.execute.mock.calls[0][0];
  expect(payload.databaseConnection.connectionId).toBe(postgresConnection._id.toString());
  expect(payload.databaseConnection.databaseType).toBe("postgresql");
  expect(payload.databaseConnection.dialect).toBe("postgres");
  expect(payload.databaseConnection.credentialEnvironmentVariableName).toBe("POSTGRES_DEMO_URL");

  expect(sqlClient.execute).toHaveBeenCalledTimes(1);
});

test("selected MySQL option cannot be executed against a PostgreSQL request body override", async () => {
  const user = await createUser();
  const mysqlConnection = await DatabaseConnection.create({
    connectionName: "MySQL Demo",
    databaseType: "mysql",
    dialect: "mysql",
    credentialEnvironmentVariableName: "MYSQL_DEMO_URL",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  const postgresConnection = await DatabaseConnection.create({
    connectionName: "PostgreSQL Demo",
    databaseType: "postgresql",
    dialect: "postgres",
    credentialEnvironmentVariableName: "POSTGRES_DEMO_URL",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  const sqliteConnection = await DatabaseConnection.create({
    connectionName: "SQLite Demo",
    databaseType: "sqlite",
    dialect: "sqlite",
    credentialEnvironmentVariableName: "SQLITE_DEMO_PATH",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  await AccessPolicy.create({
    role: ROLES.USER,
    databaseConnectionId: mysqlConnection._id,
    allowedOperations: ["SELECT"],
    allowedTables: ["Employee"],
    blockedTables: [],
    allowedColumns: [],
    active: true,
  });
  await SelectedQuery.create({
    userId: user._id,
    databaseConnectionId: mysqlConnection._id,
    optionId: 1,
    title: "MySQL employees",
    generatedSql: "SELECT employee_id, name FROM Employee",
    queryType: "SELECT",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000),
  });
  sqlClient.execute.mockResolvedValue({
    success: true,
    message: "SELECT executed successfully.",
    generatedSql: "SELECT employee_id, name FROM Employee",
    finalEnforcedSql: "SELECT employee_id, name FROM Employee",
    queryType: "SELECT",
    rowsAffected: 0,
    resultRows: [],
    executionAllowed: true,
  });

  const response = await request(app)
    .post("/api/queries/execute")
    .set("Authorization", `Bearer ${await login()}`)
    .send({databaseConnectionId: postgresConnection._id.toString(), confirmed: false});

  expect(response.status).toBe(200);
  const payload = sqlClient.execute.mock.calls[0][0];
  expect(payload.databaseConnection.connectionId).toBe(mysqlConnection._id.toString());
  expect(payload.databaseConnection.databaseType).toBe("mysql");
  expect(payload.databaseConnection.dialect).toBe("mysql");
  expect(payload.databaseConnection.credentialEnvironmentVariableName).toBe("MYSQL_DEMO_URL");

  expect(sqlClient.execute).toHaveBeenCalledTimes(1);
});
