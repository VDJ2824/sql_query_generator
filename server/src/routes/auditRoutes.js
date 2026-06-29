const express = require("express");
const AuditLog = require("../models/AuditLog");
const asyncHandler = require("../middleware/asyncHandler");
const {authenticate} = require("../middleware/authMiddleware");
const {requireRoles} = require("../middleware/roleMiddleware");
const {ROLES} = require("../constants/roles");

const router = express.Router();

router.get(
  "/audit-logs",
  authenticate,
  requireRoles(ROLES.ADMIN),
  asyncHandler(async (req, res) => {
    const filter = {};
    if (req.query.userId) filter.userId = req.query.userId;
    if (req.query.status) filter.status = req.query.status;
    if (req.query.action) filter.action = req.query.action;
    if (req.query.databaseConnectionId) filter.databaseConnectionId = req.query.databaseConnectionId;

    const logs = await AuditLog.find(filter).sort({createdAt: -1}).limit(200);
    return res.json({
      auditLogs: logs.map((log) => ({
        id: log._id.toString(),
        userId: log.userId ? log.userId.toString() : null,
        action: log.action,
        databaseConnectionId: log.databaseConnectionId ? log.databaseConnectionId.toString() : null,
        generatedSql: log.generatedSql,
        finalEnforcedSql: log.finalEnforcedSql,
        status: log.status,
        message: log.message,
        createdAt: log.createdAt,
      })),
    });
  }),
);

module.exports = router;
