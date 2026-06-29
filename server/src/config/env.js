const path = require("path");
const dotenv = require("dotenv");

function resolveRepoRoot() {
  return path.resolve(__dirname, "../../..");
}

function loadEnvironment(options = {}) {
  const repoRoot = options.repoRoot || resolveRepoRoot();
  const serverRoot = options.serverRoot || path.join(repoRoot, "server");

  dotenv.config({path: path.join(repoRoot, ".env.cloud"), override: false});
  dotenv.config({path: path.join(serverRoot, ".env"), override: false});
}

loadEnvironment();

module.exports = {
  loadEnvironment,
  resolveRepoRoot,
};
