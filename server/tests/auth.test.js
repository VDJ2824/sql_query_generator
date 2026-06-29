const request = require("supertest");
const User = require("../src/models/User");
const {ROLES} = require("../src/constants/roles");
const {createToken, hashPassword} = require("../src/utils/auth");
const {migrateLegacyRoles} = require("../src/migrations/migrateLegacyRoles");
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

async function createUser(overrides = {}) {
  return User.create({
    username: "admin",
    email: "admin@example.com",
    passwordHash: await hashPassword("admin123"),
    role: ROLES.ADMIN,
    active: true,
    ...overrides,
  });
}

test("valid login returns a JWT and safe user object", async () => {
  await createUser();

  const challenge = await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "admin123"});
  const response = await request(app)
    .post("/api/auth/verify-login-otp")
    .send({email: "admin@example.com", otp: challenge.body.debugOtp});

  expect(response.status).toBe(200);
  expect(response.body.accessToken).toBeTruthy();
  expect(response.body.user.role).toBe(ROLES.ADMIN);
  expect(response.body.user.passwordHash).toBeUndefined();
  expect(response.body.user.workspaceIdentifier).toBeUndefined();
  expect(response.body.user.postgresWorkspaceName).toBeUndefined();
  expect(response.body.user.tidbWorkspaceName).toBeUndefined();
  expect(response.body.user.lastLoginAt).toBeTruthy();
});

test("valid login verifies credentials from MongoDB and stores last login time", async () => {
  const user = await createUser();

  const challenge = await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "admin123"});
  const response = await request(app)
    .post("/api/auth/verify-login-otp")
    .send({email: "admin@example.com", otp: challenge.body.debugOtp});
  const updatedUser = await User.findById(user._id);

  expect(response.status).toBe(200);
  expect(updatedUser.lastLoginAt).toBeInstanceOf(Date);
});

test("invalid password is rejected", async () => {
  await createUser();

  const response = await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "wrong"});

  expect(response.status).toBe(401);
});

test("JWT verification allows access to /api/auth/me", async () => {
  await createUser();
  const challenge = await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "admin123"});
  const login = await request(app)
    .post("/api/auth/verify-login-otp")
    .send({email: "admin@example.com", otp: challenge.body.debugOtp});

  const response = await request(app)
    .get("/api/auth/me")
    .set("Authorization", `Bearer ${login.body.accessToken}`);

  expect(response.status).toBe(200);
  expect(response.body.user.username).toBe("admin");
  expect(response.body.user.passwordHash).toBeUndefined();
  expect(response.body.user.workspaceIdentifier).toBeUndefined();
  expect(response.body.user.postgresWorkspaceName).toBeUndefined();
  expect(response.body.user.tidbWorkspaceName).toBeUndefined();
});

test("missing JWT is rejected", async () => {
  const response = await request(app).get("/api/auth/me");

  expect(response.status).toBe(401);
});

test("password login creates an OTP challenge without returning a JWT", async () => {
  await createUser();

  const response = await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "admin123"});
  const storedUser = await User.findOne({username: "admin"}).select("+loginOtpHash +loginOtpExpiresAt");

  expect(response.status).toBe(200);
  expect(response.body.verificationRequired).toBe(true);
  expect(response.body.accessToken).toBeUndefined();
  expect(response.body.debugOtp).toMatch(/^\d{6}$/);
  expect(storedUser.loginOtpHash).toBeTruthy();
  expect(storedUser.loginOtpHash).not.toBe(response.body.debugOtp);
  expect(storedUser.loginOtpExpiresAt).toBeInstanceOf(Date);
});

test("invalid login OTP is rejected", async () => {
  await createUser();

  await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "admin123"});
  const response = await request(app)
    .post("/api/auth/verify-login-otp")
    .send({email: "admin@example.com", otp: "000000"});

  expect(response.status).toBe(401);
});

test("public registration always creates USER and ignores business-profile fields", async () => {
  const response = await request(app)
    .post("/api/auth/register")
    .send({
      username: "mallory",
      email: "mallory@example.com",
      password: "Password123",
      confirmPassword: "Password123",
      role: ROLES.ADMIN,
      department: "Finance",
      employeeId: 999,
      studentId: 999,
    });

  expect(response.status).toBe(201);
  expect(response.body.user.role).toBe(ROLES.USER);
  expect(response.body.user.active).toBe(true);
  expect(response.body.user.department).toBeUndefined();
  expect(response.body.user.employeeId).toBeUndefined();
  expect(response.body.user.studentId).toBeUndefined();
});

test("public registration stores user details in MongoDB with a bcrypt password hash", async () => {
  const response = await request(app)
    .post("/api/auth/register")
    .send({
      username: "stored_user",
      email: "stored.user@example.com",
      password: "Password123",
      confirmPassword: "Password123",
    });

  const storedUser = await User.findOne({username: "stored_user"}).select("+passwordHash");

  expect(response.status).toBe(201);
  expect(storedUser).toBeTruthy();
  expect(storedUser.email).toBe("stored.user@example.com");
  expect(storedUser.role).toBe(ROLES.USER);
  expect(storedUser.workspaceIdentifier).toMatch(/^user_stored_user_[a-f0-9]{6}$/);
  expect(storedUser.postgresWorkspaceName).toBe(storedUser.workspaceIdentifier);
  expect(storedUser.tidbWorkspaceName).toBe(storedUser.workspaceIdentifier);
  expect(storedUser.passwordHash).not.toBe("Password123");
  expect(storedUser.passwordHash).toMatch(/^\$2[aby]\$/);
  expect(response.body.user.passwordHash).toBeUndefined();
  expect(response.body.user.workspaceIdentifier).toBeUndefined();
  expect(response.body.user.postgresWorkspaceName).toBeUndefined();
  expect(response.body.user.tidbWorkspaceName).toBeUndefined();
});

test("public registration requires matching confirmPassword", async () => {
  const response = await request(app)
    .post("/api/auth/register")
    .send({
      username: "mismatch",
      email: "mismatch@example.com",
      password: "Password123",
      confirmPassword: "Different123",
    });

  expect(response.status).toBe(400);
});

test("existing EMPLOYEE user becomes USER after migration", async () => {
  await User.collection.insertOne({
    username: "legacy_employee",
    email: "legacy.employee@example.com",
    passwordHash: await hashPassword("Password123"),
    role: "EMPLOYEE",
    department: "IT",
    employeeId: 10,
    active: true,
  });

  const result = await migrateLegacyRoles({log: jest.fn()});
  const migrated = await User.findOne({username: "legacy_employee"});

  expect(result.migratedUsers).toBe(1);
  expect(migrated.role).toBe(ROLES.USER);
  expect(migrated.toSafeJSON().department).toBeUndefined();
});

test("existing MANAGER user becomes USER after migration", async () => {
  await User.collection.insertOne({
    username: "legacy_manager",
    email: "legacy.manager@example.com",
    passwordHash: await hashPassword("Password123"),
    role: "MANAGER",
    department: "Finance",
    managerId: 2,
    active: true,
  });

  await migrateLegacyRoles({log: jest.fn()});
  const migrated = await User.findOne({username: "legacy_manager"});

  expect(migrated.role).toBe(ROLES.USER);
});

test("ADMIN remains ADMIN after migration", async () => {
  await createUser();

  await migrateLegacyRoles({log: jest.fn()});
  const admin = await User.findOne({username: "admin"});

  expect(admin.role).toBe(ROLES.ADMIN);
});

test("/api/auth/me returns latest MongoDB role instead of stale token role", async () => {
  const user = await createUser({role: ROLES.ADMIN});
  const staleAdminToken = createToken(user);
  await User.updateOne({_id: user._id}, {$set: {role: ROLES.USER}});

  const response = await request(app)
    .get("/api/auth/me")
    .set("Authorization", `Bearer ${staleAdminToken}`);

  expect(response.status).toBe(200);
  expect(response.body.user.role).toBe(ROLES.USER);
});
