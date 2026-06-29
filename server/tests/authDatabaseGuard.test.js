const mongoose = require("mongoose");
const request = require("supertest");
const createApp = require("../src/app");

afterAll(async () => {
  await mongoose.disconnect();
});

test("login checks MongoDB connection before verifying credentials", async () => {
  await mongoose.disconnect();
  const app = createApp();

  const response = await request(app)
    .post("/api/auth/login")
    .send({email: "admin@example.com", password: "admin123"});

  expect(response.status).toBe(503);
  expect(response.body.message).toMatch(/database is not connected/i);
});

test("registration checks MongoDB connection before saving user details", async () => {
  await mongoose.disconnect();
  const app = createApp();

  const response = await request(app)
    .post("/api/auth/register")
    .send({
      username: "offline_user",
      email: "offline@example.com",
      password: "Password123",
      confirmPassword: "Password123",
    });

  expect(response.status).toBe(503);
  expect(response.body.message).toMatch(/user details cannot be saved/i);
});

test("health endpoint reports MongoDB connection state", async () => {
  await mongoose.disconnect();
  const app = createApp();
  process.env.MONGODB_URI = "mongodb+srv://secret-user:secret-password@example.invalid/app";
  process.env.SQL_SERVICE_API_KEY = "super-secret-internal-key";

  const response = await request(app).get("/api/health");
  const serialized = JSON.stringify(response.body);

  expect(response.status).toBe(200);
  expect(response.body.database).toEqual({
    connected: false,
    state: "disconnected",
  });
  expect(serialized).not.toContain("secret-password");
  expect(serialized).not.toContain("super-secret-internal-key");
  delete process.env.MONGODB_URI;
  delete process.env.SQL_SERVICE_API_KEY;
});

test("CORS allows both localhost and 127.0.0.1 Vite origins in local development", async () => {
  await mongoose.disconnect();
  const app = createApp();

  const localhostPreflight = await request(app)
    .options("/api/auth/login")
    .set("Origin", "http://localhost:5173")
    .set("Access-Control-Request-Method", "POST");
  const loopbackPreflight = await request(app)
    .options("/api/auth/login")
    .set("Origin", "http://127.0.0.1:5173")
    .set("Access-Control-Request-Method", "POST");

  expect(localhostPreflight.headers["access-control-allow-origin"]).toBe("http://localhost:5173");
  expect(loopbackPreflight.headers["access-control-allow-origin"]).toBe("http://127.0.0.1:5173");
});
