const mongoose = require("mongoose");
const {loadEnvironment} = require("../src/config/env");
const {connectDatabase, disconnectDatabase} = require("../src/config/database");
const User = require("../src/models/User");
const {ensureUserWorkspaceMetadata} = require("../src/services/workspaceService");

async function backfillWorkspaces({log = console.log} = {}) {
  const users = await User.find({});
  let updatedUsers = 0;

  for (const user of users) {
    const before = [
      user.workspaceIdentifier,
      user.postgresWorkspaceName,
      user.tidbWorkspaceName,
    ].join("|");
    await ensureUserWorkspaceMetadata(user);
    const after = [
      user.workspaceIdentifier,
      user.postgresWorkspaceName,
      user.tidbWorkspaceName,
    ].join("|");
    if (before !== after) {
      updatedUsers += 1;
    }
  }

  log(`Workspace metadata backfill complete. Updated users: ${updatedUsers}.`);
  return {updatedUsers};
}

async function run() {
  loadEnvironment();
  await connectDatabase();
  try {
    await backfillWorkspaces();
  } finally {
    await disconnectDatabase();
    await mongoose.connection.close().catch(() => {});
  }
}

if (require.main === module) {
  run().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}

module.exports = {
  backfillWorkspaces,
};
