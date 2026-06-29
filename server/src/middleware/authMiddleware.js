const User = require("../models/User");
const {verifyToken} = require("../utils/auth");
const {ensureUserWorkspaceMetadata} = require("../services/workspaceService");

async function authenticate(req, res, next) {
  try {
    const header = req.headers.authorization || "";
    const [scheme, token] = header.split(" ");
    if (scheme !== "Bearer" || !token) {
      return res.status(401).json({message: "Authentication token is required."});
    }

    const payload = verifyToken(token);
    const user = await User.findById(payload.sub);
    if (!user || !user.active) {
      return res.status(401).json({message: "Invalid or inactive user."});
    }

    req.user = await ensureUserWorkspaceMetadata(user);
    return next();
  } catch (error) {
    return res.status(401).json({message: "Invalid or expired token."});
  }
}

module.exports = {
  authenticate,
};
