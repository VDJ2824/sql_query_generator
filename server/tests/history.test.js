const request = require("supertest");
const mongoose = require("mongoose");
const User = require("../src/models/User");
const AuditLog = require("../src/models/AuditLog");
const QueryHistory = require("../src/models/QueryHistory");
const {ROLES} = require("../src/constants/roles");
const {hashPassword} = require("../src/utils/auth");
const {clearDatabase, startTestApp, stopTestApp} = require("./helpers/testServer");

let app;

beforeAll(async () => {
  app = await startTestApp();
});

afterAll(async () => {
  await stopTestApp();
});

beforeEach(async () => {
  await clearDatabase();
});

async function createUser(username) {
  return User.create({
    username,
    email: `${username}@example.com`,
    passwordHash: await hashPassword("Password123"),
    role: ROLES.USER,
    active: true,
  });
}

async function createAdmin(username = "admin") {
  return User.create({
    username,
    email: `${username}@example.com`,
    passwordHash: await hashPassword("Password123"),
    role: ROLES.ADMIN,
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

test("users can see only their own query history", async () => {
  const alice = await createUser("alice");
  const bob = await createUser("bob");
  const databaseConnectionId = new mongoose.Types.ObjectId();

  await QueryHistory.create([
    {
      userId: alice._id,
      databaseConnectionId,
      userPrompt: "alice prompt",
      generatedSql: "SELECT 1",
      finalEnforcedSql: "SELECT 1",
      queryType: "SELECT",
      executionStatus: "executed",
      rowsAffected: 1,
    },
    {
      userId: bob._id,
      databaseConnectionId,
      userPrompt: "bob prompt",
      generatedSql: "SELECT 2",
      finalEnforcedSql: "SELECT 2",
      queryType: "SELECT",
      executionStatus: "executed",
      rowsAffected: 1,
    },
  ]);

  const response = await request(app)
    .get("/api/history")
    .set("Authorization", `Bearer ${await tokenFor("alice")}`);

  expect(response.status).toBe(200);
  expect(response.body.history).toHaveLength(1);
  expect(response.body.history[0].userPrompt).toBe("alice prompt");
  expect(JSON.stringify(response.body)).not.toContain("bob prompt");
});

test("USER cannot access audit logs", async () => {
  await createUser("alice");

  const response = await request(app)
    .get("/api/admin/audit-logs")
    .set("Authorization", `Bearer ${await tokenFor("alice")}`);

  expect(response.status).toBe(403);
});

test("ADMIN can access audit logs", async () => {
  const admin = await createAdmin();
  await AuditLog.create({
    userId: admin._id,
    action: "TEST_AUDIT",
    status: "success",
    message: "audit visibility test",
  });

  const response = await request(app)
    .get("/api/admin/audit-logs")
    .set("Authorization", `Bearer ${await tokenFor("admin")}`);

  expect(response.status).toBe(200);
  expect(response.body.auditLogs.map((log) => log.action)).toContain("TEST_AUDIT");
});
