const mongoose = require("mongoose");
const {MongoMemoryServer} = require("mongodb-memory-server");
const createApp = require("../../src/app");

let mongoServer;
jest.setTimeout(30000);

async function startTestApp() {
  process.env.JWT_SECRET = "test-jwt-secret";
  process.env.JWT_EXPIRES_IN = "1h";
  mongoServer = await MongoMemoryServer.create();
  await mongoose.connect(mongoServer.getUri());
  return createApp();
}

async function stopTestApp() {
  await mongoose.disconnect();
  if (mongoServer) {
    await mongoServer.stop();
  }
}

async function clearDatabase() {
  const collections = await mongoose.connection.db.collections();
  for (const collection of collections) {
    await collection.deleteMany({});
  }
}

module.exports = {
  clearDatabase,
  startTestApp,
  stopTestApp,
};
