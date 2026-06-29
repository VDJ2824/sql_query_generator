const createApp = require("./app");
const {connectDatabase} = require("./config/database");
const {migrateLegacyRoles} = require("./migrations/migrateLegacyRoles");

const port = process.env.PORT || 5000;

async function startServer() {
  await connectDatabase();
  await migrateLegacyRoles();
  const app = createApp();
  app.listen(port, () => {
    console.log(`MERN server running on port ${port}`);
  });
}

startServer().catch((error) => {
  console.error("Failed to start server:", error.message);
  process.exit(1);
});
