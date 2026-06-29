export const SUPPORTED_ROLES = Object.freeze({
  ADMIN: "ADMIN",
  USER: "USER",
});

export function normalizeRole(role) {
  return role === SUPPORTED_ROLES.ADMIN ? SUPPORTED_ROLES.ADMIN : SUPPORTED_ROLES.USER;
}

export function normalizeUser(user) {
  if (!user) return null;
  const {
    workspaceIdentifier,
    postgresWorkspaceName,
    tidbWorkspaceName,
    ...safeUser
  } = user;
  return {
    ...safeUser,
    role: normalizeRole(user.role),
  };
}
