function sanitizeWorkspacePart(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized || "user";
}

function workspaceNameForUser(user) {
  if (!user || !user._id) {
    throw new Error("A persisted MongoDB user is required before generating workspace metadata.");
  }
  const usernamePart = sanitizeWorkspacePart(user.username).slice(0, 32);
  const idSuffix = user._id.toString().slice(-6).toLowerCase();
  return `user_${usernamePart}_${idSuffix}`;
}

function workspaceMetadataForUser(user) {
  const workspaceName = workspaceNameForUser(user);
  return {
    workspaceIdentifier: workspaceName,
    postgresWorkspaceName: workspaceName,
    tidbWorkspaceName: workspaceName,
    postgresProvisioningStatus: user.postgresProvisioningStatus || "pending",
    tidbProvisioningStatus: user.tidbProvisioningStatus || "pending",
  };
}

async function ensureUserWorkspaceMetadata(user) {
  const missingWorkspace = !user.workspaceIdentifier || !user.postgresWorkspaceName || !user.tidbWorkspaceName;
  if (!missingWorkspace) {
    return user;
  }

  const metadata = workspaceMetadataForUser(user);
  user.workspaceIdentifier = user.workspaceIdentifier || metadata.workspaceIdentifier;
  user.postgresWorkspaceName = user.postgresWorkspaceName || metadata.postgresWorkspaceName;
  user.tidbWorkspaceName = user.tidbWorkspaceName || metadata.tidbWorkspaceName;
  user.postgresProvisioningStatus = user.postgresProvisioningStatus || metadata.postgresProvisioningStatus;
  user.tidbProvisioningStatus = user.tidbProvisioningStatus || metadata.tidbProvisioningStatus;
  await user.save();
  return user;
}

module.exports = {
  ensureUserWorkspaceMetadata,
  sanitizeWorkspacePart,
  workspaceMetadataForUser,
  workspaceNameForUser,
};
