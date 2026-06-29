const AuditLog = require("../models/AuditLog");
const {redactSensitiveText} = require("../utils/redact");

async function writeAuditLog({
  userId = null,
  action,
  databaseConnectionId = null,
  generatedSql = "",
  finalEnforcedSql = "",
  status,
  message = "",
}) {
  return AuditLog.create({
    userId,
    action,
    databaseConnectionId,
    generatedSql: redactSensitiveText(generatedSql),
    finalEnforcedSql: redactSensitiveText(finalEnforcedSql),
    status,
    message: redactSensitiveText(message),
  });
}

module.exports = {
  writeAuditLog,
};
