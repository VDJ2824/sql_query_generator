const mongoose = require("mongoose");
const {ROLES} = require("../constants/roles");

function normalizeRole(role) {
  return role === ROLES.ADMIN ? ROLES.ADMIN : ROLES.USER;
}

const userSchema = new mongoose.Schema(
  {
    username: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      lowercase: true,
    },
    email: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      lowercase: true,
    },
    passwordHash: {
      type: String,
      required: true,
      select: false,
    },
    role: {
      type: String,
      enum: Object.values(ROLES),
      default: ROLES.USER,
      required: true,
    },
    active: {
      type: Boolean,
      default: true,
    },
    lastLoginAt: {
      type: Date,
      default: null,
    },
    loginOtpHash: {
      type: String,
      default: null,
      select: false,
    },
    loginOtpExpiresAt: {
      type: Date,
      default: null,
      select: false,
    },
    workspaceIdentifier: {
      type: String,
      default: "",
      index: true,
    },
    postgresWorkspaceName: {
      type: String,
      default: "",
    },
    tidbWorkspaceName: {
      type: String,
      default: "",
    },
    postgresProvisioningStatus: {
      type: String,
      enum: ["pending", "provisioning", "ready", "failed"],
      default: "pending",
    },
    tidbProvisioningStatus: {
      type: String,
      enum: ["pending", "provisioning", "ready", "failed"],
      default: "pending",
    },
  },
  {
    timestamps: {createdAt: "createdAt", updatedAt: "updatedAt"},
    collection: "users",
  },
);

userSchema.methods.toSafeJSON = function toSafeJSON() {
  return {
    id: this._id.toString(),
    username: this.username,
    email: this.email,
    role: normalizeRole(this.role),
    active: this.active,
    createdAt: this.createdAt,
    lastLoginAt: this.lastLoginAt,
  };
};

module.exports = mongoose.model("User", userSchema);
module.exports.normalizeRole = normalizeRole;
