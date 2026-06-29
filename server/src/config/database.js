const mongoose = require("mongoose");

function getDatabaseConnectionState() {
  return mongoose.STATES[mongoose.connection.readyState] || "unknown";
}

function isDatabaseConnected() {
  return mongoose.connection.readyState === 1;
}

async function connectDatabase(uri = process.env.MONGODB_URI || process.env.MONGO_URI) {
  if (!uri) {
    throw new Error("MONGODB_URI is required.");
  }
  mongoose.set("strictQuery", true);
  await mongoose.connect(uri);
}

async function disconnectDatabase() {
  await mongoose.disconnect();
}

module.exports = {
  connectDatabase,
  disconnectDatabase,
  getDatabaseConnectionState,
  isDatabaseConnected,
};
