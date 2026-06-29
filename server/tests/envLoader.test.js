const fs = require("fs");
const os = require("os");
const path = require("path");
const {loadEnvironment} = require("../src/config/env");

const TEST_KEYS = ["CLOUD_LOADER_TEST_VALUE", "CLOUD_LOADER_SERVICE_VALUE"];

afterEach(() => {
  for (const key of TEST_KEYS) {
    delete process.env[key];
  }
});

function tempProject() {
  const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), "sql-generator-env-"));
  const serverRoot = path.join(repoRoot, "server");
  fs.mkdirSync(serverRoot, {recursive: true});
  return {repoRoot, serverRoot};
}

test("Express env loader reads harmless values from root .env.cloud", () => {
  const {repoRoot, serverRoot} = tempProject();
  fs.writeFileSync(path.join(repoRoot, ".env.cloud"), "CLOUD_LOADER_TEST_VALUE=from-cloud\n");

  loadEnvironment({repoRoot, serverRoot});

  expect(process.env.CLOUD_LOADER_TEST_VALUE).toBe("from-cloud");
});

test("Express env loader keeps existing process env values above .env.cloud", () => {
  const {repoRoot, serverRoot} = tempProject();
  process.env.CLOUD_LOADER_TEST_VALUE = "from-process";
  fs.writeFileSync(path.join(repoRoot, ".env.cloud"), "CLOUD_LOADER_TEST_VALUE=from-cloud\n");

  loadEnvironment({repoRoot, serverRoot});

  expect(process.env.CLOUD_LOADER_TEST_VALUE).toBe("from-process");
});

test("Express env loader uses service .env only when root cloud file lacks the value", () => {
  const {repoRoot, serverRoot} = tempProject();
  fs.writeFileSync(path.join(repoRoot, ".env.cloud"), "CLOUD_LOADER_TEST_VALUE=from-cloud\n");
  fs.writeFileSync(path.join(serverRoot, ".env"), [
    "CLOUD_LOADER_TEST_VALUE=from-service",
    "CLOUD_LOADER_SERVICE_VALUE=service-only",
  ].join("\n"));

  loadEnvironment({repoRoot, serverRoot});

  expect(process.env.CLOUD_LOADER_TEST_VALUE).toBe("from-cloud");
  expect(process.env.CLOUD_LOADER_SERVICE_VALUE).toBe("service-only");
});
