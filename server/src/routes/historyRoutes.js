const express = require("express");
const QueryHistory = require("../models/QueryHistory");
const asyncHandler = require("../middleware/asyncHandler");
const {authenticate} = require("../middleware/authMiddleware");

const router = express.Router();

router.get(
  "/",
  authenticate,
  asyncHandler(async (req, res) => {
    const history = await QueryHistory.find({userId: req.user._id})
      .sort({createdAt: -1})
      .limit(100);

    return res.json({
      history: history.map((item) => ({
        id: item._id.toString(),
        userId: item.userId.toString(),
        databaseConnectionId: item.databaseConnectionId.toString(),
        userPrompt: item.userPrompt,
        generatedSql: item.generatedSql,
        finalEnforcedSql: item.finalEnforcedSql,
        queryType: item.queryType,
        executionStatus: item.executionStatus,
        rowsAffected: item.rowsAffected,
        createdAt: item.createdAt,
      })),
    });
  }),
);

module.exports = router;
