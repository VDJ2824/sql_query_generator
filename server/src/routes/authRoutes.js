const express = require("express");
const User = require("../models/User");
const asyncHandler = require("../middleware/asyncHandler");
const {authenticate} = require("../middleware/authMiddleware");
const {ROLES} = require("../constants/roles");
const {isDatabaseConnected} = require("../config/database");
const {
  createToken,
  generateLoginOtp,
  hashPassword,
  loginOtpExpiresAt,
  verifyPassword,
} = require("../utils/auth");
const {writeAuditLog} = require("../services/auditService");
const {sendLoginOtp} = require("../services/emailService");
const {ensureUserWorkspaceMetadata} = require("../services/workspaceService");

const router = express.Router();

router.post(
  "/register",
  asyncHandler(async (req, res) => {
    if (!isDatabaseConnected()) {
      return res.status(503).json({
        message: "Authentication database is not connected. User details cannot be saved right now.",
      });
    }

    const {username, email, password, confirmPassword} = req.body;
    if (!username || !email || !password || !confirmPassword) {
      return res.status(400).json({message: "username, email, password, and confirmPassword are required."});
    }
    if (password !== confirmPassword) {
      return res.status(400).json({message: "password and confirmPassword must match."});
    }

    const existingUser = await User.findOne({
      $or: [{username: username.toLowerCase()}, {email: email.toLowerCase()}],
    });
    if (existingUser) {
      return res.status(409).json({message: "Username or email already exists."});
    }

    const user = await User.create({
      username,
      email,
      passwordHash: await hashPassword(password),
      role: ROLES.USER,
      active: true,
    });
    await ensureUserWorkspaceMetadata(user);

    await writeAuditLog({
      userId: user._id,
      action: "AUTH_REGISTER",
      status: "success",
      message: `Registered user ${user.username}`,
    });

    return res.status(201).json({user: user.toSafeJSON()});
  }),
);

router.post(
  "/login",
  asyncHandler(async (req, res) => {
    if (!isDatabaseConnected()) {
      return res.status(503).json({
        message: "Authentication database is not connected. Please try again after the server reconnects.",
      });
    }

    const {email, password} = req.body;
    if (!email || !password) {
      return res.status(400).json({message: "email and password are required."});
    }

    const normalizedEmail = email.toLowerCase();
    const user = await User.findOne({email: normalizedEmail}).select(
      "+passwordHash +loginOtpHash +loginOtpExpiresAt",
    );
    if (!user || !user.active || !(await verifyPassword(password, user.passwordHash))) {
      await writeAuditLog({
        action: "AUTH_LOGIN",
        status: "failure",
        message: `Failed login for email=${normalizedEmail}`,
      });
      return res.status(401).json({message: "Invalid email or password."});
    }

    const otp = generateLoginOtp();
    const expiresAt = loginOtpExpiresAt();
    user.loginOtpHash = await hashPassword(otp);
    user.loginOtpExpiresAt = expiresAt;
    await user.save();
    await ensureUserWorkspaceMetadata(user);

    const expiresInMinutes = Number.parseInt(process.env.LOGIN_OTP_EXPIRES_IN_MINUTES || "10", 10) || 10;
    const emailSent = await sendLoginOtp({
      username: user.username,
      email: user.email,
      otp,
      expiresInMinutes,
    });

    await writeAuditLog({
      userId: user._id,
      action: "AUTH_LOGIN",
      status: "success",
      message: `Login OTP challenge created for ${user.username}`,
    });

    return res.json({
      message: "Login OTP sent",
      username: user.username,
      email: user.email,
      verificationRequired: true,
      expiresInMinutes,
      emailSent,
      debugOtp: process.env.NODE_ENV === "production" ? undefined : otp,
    });
  }),
);

router.post(
  "/verify-login-otp",
  asyncHandler(async (req, res) => {
    if (!isDatabaseConnected()) {
      return res.status(503).json({
        message: "Authentication database is not connected. Please try again after the server reconnects.",
      });
    }

    const {email, otp} = req.body;
    if (!email || !otp) {
      return res.status(400).json({message: "email and otp are required."});
    }

    const normalizedEmail = email.toLowerCase();
    const user = await User.findOne({email: normalizedEmail}).select(
      "+loginOtpHash +loginOtpExpiresAt",
    );
    const otpValue = String(otp).trim();
    const otpExpired = user?.loginOtpExpiresAt ? user.loginOtpExpiresAt.getTime() < Date.now() : true;
    const otpMatches = user?.loginOtpHash ? await verifyPassword(otpValue, user.loginOtpHash) : false;

    if (!user || !user.active || otpExpired || !otpMatches) {
      await writeAuditLog({
        userId: user?._id,
        action: "AUTH_LOGIN_OTP",
        status: "failure",
        message: `Failed login OTP verification for email=${normalizedEmail}`,
      });
      return res.status(401).json({message: "Invalid or expired OTP."});
    }

    user.loginOtpHash = null;
    user.loginOtpExpiresAt = null;
    user.lastLoginAt = new Date();
    await user.save();
    await ensureUserWorkspaceMetadata(user);

    await writeAuditLog({
      userId: user._id,
      action: "AUTH_LOGIN_OTP",
      status: "success",
      message: `Login OTP verified for ${user.username}`,
    });

    const token = createToken(user);
    return res.json({
      accessToken: token,
      tokenType: "Bearer",
      user: user.toSafeJSON(),
    });
  }),
);

router.get(
  "/me",
  authenticate,
  asyncHandler(async (req, res) => res.json({user: req.user.toSafeJSON()})),
);

module.exports = router;
