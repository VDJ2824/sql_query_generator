const mongoose = require("mongoose");
const User = require("../src/models/User");
const {ROLES} = require("../src/constants/roles");
const {hashPassword} = require("../src/utils/auth");
const {backfillWorkspaces} = require("../scripts/backfillWorkspaces");
const {
  sanitizeWorkspacePart,
  workspaceNameForUser,
} = require("../src/services/workspaceService");
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
    email: `${sanitizeWorkspacePart(username)}-${new mongoose.Types.ObjectId().toString().slice(-6)}@example.com`,
    passwordHash: await hashPassword("Password123"),
    role: ROLES.USER,
    active: true,
  });
}

test("workspace name is generated from sanitized username plus MongoDB ID suffix", async () => {
  const user = await createUser("Varima Dudeja!");
  const workspace = workspaceNameForUser(user);

  expect(workspace).toMatch(/^user_varima_dudeja_[a-f0-9]{6}$/);
});

test("two users with same sanitized username receive different workspace names", async () => {
  const first = await createUser("same.user");
  const second = await createUser("same user");

  expect(sanitizeWorkspacePart(first.username)).toBe(sanitizeWorkspacePart(second.username));
  expect(workspaceNameForUser(first)).not.toBe(workspaceNameForUser(second));
});

test("backfill adds missing workspace metadata without deleting users", async () => {
  await createUser("legacy_workspace_user");

  const result = await backfillWorkspaces({log: jest.fn()});
  const user = await User.findOne({username: "legacy_workspace_user"});

  expect(result.updatedUsers).toBe(1);
  expect(user.workspaceIdentifier).toMatch(/^user_legacy_workspace_user_[a-f0-9]{6}$/);
  expect(user.postgresWorkspaceName).toBe(user.workspaceIdentifier);
  expect(user.tidbWorkspaceName).toBe(user.workspaceIdentifier);
  expect(user.postgresProvisioningStatus).toBe("pending");
  expect(user.tidbProvisioningStatus).toBe("pending");
});
