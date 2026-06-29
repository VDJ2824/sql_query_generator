const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const crypto = require("crypto");
const {ROLES} = require("../constants/roles");

const SALT_ROUNDS = 12;

function getJwtSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error("JWT_SECRET is required.");
  }
  return secret;
}

async function hashPassword(password) {
  return bcrypt.hash(password, SALT_ROUNDS);
}

async function verifyPassword(password, passwordHash) {
  return bcrypt.compare(password, passwordHash);
}

function createToken(user) {
  return jwt.sign(
    {
      sub: user._id.toString(),
      role: user.role === ROLES.ADMIN ? ROLES.ADMIN : ROLES.USER,
      username: user.username,
    },
    getJwtSecret(),
    {expiresIn: process.env.JWT_EXPIRES_IN || "1h"},
  );
}

function verifyToken(token) {
  return jwt.verify(token, getJwtSecret());
}

function generateLoginOtp() {
  return crypto.randomInt(0, 1_000_000).toString().padStart(6, "0");
}

function loginOtpExpiresAt() {
  const minutes = Number.parseInt(process.env.LOGIN_OTP_EXPIRES_IN_MINUTES || "10", 10);
  const safeMinutes = Number.isFinite(minutes) && minutes > 0 ? minutes : 10;
  return new Date(Date.now() + safeMinutes * 60 * 1000);
}

module.exports = {
  createToken,
  generateLoginOtp,
  hashPassword,
  loginOtpExpiresAt,
  verifyPassword,
  verifyToken,
};
