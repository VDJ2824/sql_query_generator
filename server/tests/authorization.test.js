const request = require("supertest");
const User = require("../src/models/User");
const DatabaseConnection = require("../src/models/DatabaseConnection");
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
    schema: jest.fn(),
  };
  app.locals.sqlIntelligenceClient = sqlClient;
});

async function createUser(username, role) {
  return User.create({
    username,
    email: `${username}@example.com`,
    passwordHash: await hashPassword("Password123"),
    role,
    active: true,
  });
}

async function tokenFor(username) {
  const email = `${username}@example.com`;
  const challenge = await request(app)
    .post("/api/auth/login")
    .send({email, password: "Password123"});
  const response = await request(app)
    .post("/api/auth/verify-login-otp")
    .send({email, otp: challenge.body.debugOtp});
  return response.body.accessToken;
}

test("role protection blocks non-admin database connection creation", async () => {
  await createUser("normaluser", ROLES.USER);
  const token = await tokenFor("normaluser");

  const response = await request(app)
    .post("/api/database-connections")
    .set("Authorization", `Bearer ${token}`)
    .send({
      connectionName: "Production DB",
      databaseType: "postgresql",
      dialect: "postgres",
      credentialEnvironmentVariableName: "PROD_DATABASE_URL",
      allowedRoles: [ROLES.ADMIN],
    });

  expect(response.status).toBe(403);
});

test("admin can create database connection metadata without exposing credentials", async () => {
  await createUser("admin", ROLES.ADMIN);
  const token = await tokenFor("admin");

  const response = await request(app)
    .post("/api/database-connections")
    .set("Authorization", `Bearer ${token}`)
    .send({
      connectionName: "Production DB",
      databaseType: "postgresql",
      dialect: "postgres",
      credentialEnvironmentVariableName: "PROD_DATABASE_URL",
      allowedRoles: [ROLES.ADMIN],
    });

  expect(response.status).toBe(201);
  expect(response.body.databaseConnection.credentialEnvironmentVariableName).toBeUndefined();
  expect(JSON.stringify(response.body)).not.toContain("PROD_DATABASE_URL");
  expect(JSON.stringify(response.body)).not.toContain("postgres://");
});

test("admin cannot store raw target database connection strings in metadata", async () => {
  await createUser("admin", ROLES.ADMIN);
  const token = await tokenFor("admin");

  const response = await request(app)
    .post("/api/database-connections")
    .set("Authorization", `Bearer ${token}`)
    .send({
      connectionName: "Leaky DB",
      databaseType: "postgresql",
      dialect: "postgres",
      credentialEnvironmentVariableName: "postgres://user:password@localhost:5432/company",
      allowedRoles: [ROLES.ADMIN],
    });

  expect(response.status).toBe(400);
  expect(await DatabaseConnection.countDocuments({connectionName: "Leaky DB"})).toBe(0);
});

test("users see only database connections allowed for their role", async () => {
  await createUser("normaluser", ROLES.USER);
  await DatabaseConnection.create([
    {
      connectionName: "User DB",
      databaseType: "sqlite",
      dialect: "sqlite",
      credentialEnvironmentVariableName: "USER_DB_URL",
      allowedRoles: [ROLES.USER],
      active: true,
    },
    {
      connectionName: "Admin DB",
      databaseType: "mysql",
      dialect: "mysql",
      credentialEnvironmentVariableName: "ADMIN_DB_URL",
      allowedRoles: [ROLES.ADMIN],
      active: true,
    },
  ]);
  const token = await tokenFor("normaluser");

  const response = await request(app)
    .get("/api/database-connections")
    .set("Authorization", `Bearer ${token}`);

  expect(response.status).toBe(200);
  expect(response.body.databaseConnections).toHaveLength(1);
  expect(response.body.databaseConnections[0].connectionName).toBe("User DB");
  expect(response.body.databaseConnections[0].credentialEnvironmentVariableName).toBeUndefined();
});

test("users can list table names for an allowed database connection without seeing columns or credentials", async () => {
  await createUser("normaluser", ROLES.USER);
  const connection = await DatabaseConnection.create({
    connectionName: "User PostgreSQL",
    databaseType: "postgresql",
    dialect: "postgres",
    credentialEnvironmentVariableName: "USER_DB_URL",
    allowedRoles: [ROLES.USER],
    active: true,
  });
  sqlClient.schema.mockResolvedValue({
    allowedTables: [
      {tableName: "Student", allowedColumns: [{name: "email", type: "VARCHAR"}]},
      {tableName: "Course", allowedColumns: [{name: "title", type: "VARCHAR"}]},
    ],
  });

  const response = await request(app)
    .get(`/api/database-connections/${connection._id}/tables`)
    .set("Authorization", `Bearer ${await tokenFor("normaluser")}`);

  expect(response.status).toBe(200);
  expect(response.body.tables).toEqual(["Course", "Student"]);
  expect(JSON.stringify(response.body)).not.toContain("USER_DB_URL");
  expect(JSON.stringify(response.body)).not.toContain("email");
  expect(sqlClient.schema).toHaveBeenCalledWith(expect.objectContaining({
    verifiedUser: expect.objectContaining({role: ROLES.USER}),
    databaseConnection: expect.objectContaining({
      connectionId: connection._id.toString(),
      credentialEnvironmentVariableName: "USER_DB_URL",
    }),
  }));
});

test("users cannot list tables for a database connection outside their role", async () => {
  await createUser("normaluser", ROLES.USER);
  const connection = await DatabaseConnection.create({
    connectionName: "Admin MySQL",
    databaseType: "mysql",
    dialect: "mysql",
    credentialEnvironmentVariableName: "ADMIN_DB_URL",
    allowedRoles: [ROLES.ADMIN],
    active: true,
  });

  const response = await request(app)
    .get(`/api/database-connections/${connection._id}/tables`)
    .set("Authorization", `Bearer ${await tokenFor("normaluser")}`);

  expect(response.status).toBe(404);
  expect(sqlClient.schema).not.toHaveBeenCalled();
});
