import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {normalizeRole, normalizeUser} from "../src/utils/roles.js";

assert.equal(normalizeRole("ADMIN"), "ADMIN");
assert.equal(normalizeRole("USER"), "USER");
assert.equal(normalizeRole("EMPLOYEE"), "USER");
assert.equal(normalizeRole("MANAGER"), "USER");
assert.equal(normalizeRole("STUDENT"), "USER");
assert.equal(normalizeRole("FACULTY"), "USER");
assert.deepEqual(normalizeUser({username: "legacy", role: "EMPLOYEE"}), {
  username: "legacy",
  role: "USER",
});
assert.deepEqual(
  normalizeUser({
    username: "cached",
    role: "USER",
    workspaceIdentifier: "user_cached_123abc",
    postgresWorkspaceName: "user_cached_123abc",
    tidbWorkspaceName: "user_cached_123abc",
  }),
  {
    username: "cached",
    role: "USER",
  },
);

console.log("Role display fallback renders legacy roles as USER.");

function readSourceFiles(directory) {
  const entries = fs.readdirSync(directory, {withFileTypes: true});
  return entries.flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return readSourceFiles(fullPath);
    return fullPath.endsWith(".js") || fullPath.endsWith(".jsx") ? [fullPath] : [];
  });
}

const sourceFiles = readSourceFiles(path.resolve("src"));
const sourceText = sourceFiles.map((filePath) => fs.readFileSync(filePath, "utf8")).join("\n");
const nonSanitizerSourceText = sourceFiles
  .filter((filePath) => !filePath.endsWith(path.join("src", "utils", "roles.js")))
  .map((filePath) => fs.readFileSync(filePath, "utf8"))
  .join("\n");

assert.match(sourceText, /VITE_API_BASE_URL/);
assert.doesNotMatch(sourceText, /SQL_SERVICE_API_KEY|MONGODB_URI|POSTGRES_DEMO_URL|MYSQL_DEMO_URL/);
assert.doesNotMatch(sourceText, /127\.0\.0\.1:8001|localhost:8001|\/internal\/(?:schema|generate|preview|execute)/);
assert.doesNotMatch(nonSanitizerSourceText, /workspaceIdentifier|postgresWorkspaceName|tidbWorkspaceName/);

console.log("React source calls only the Express API surface and does not expose service secrets or workspace identifiers.");
