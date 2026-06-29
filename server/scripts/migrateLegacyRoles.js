require("../src/config/env");

const {connectDatabase, disconnectDatabase} = require("../src/config/database");
const {migrateLegacyRoles} = require("../src/migrations/migrateLegacyRoles");

async function main() {
  await connectDatabase();
  const result = await migrateLegacyRoles();
  await disconnectDatabase();
  console.log(JSON.stringify(result, null, 2));
}

main().catch(async (error) => {
  console.error("Failed to migrate legacy roles:", error.message);
  await disconnectDatabase();
  process.exit(1);
});
