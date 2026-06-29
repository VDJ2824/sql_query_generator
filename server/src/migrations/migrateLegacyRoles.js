const User = require("../models/User");
const {ROLES} = require("../constants/roles");

const LEGACY_ROLES = ["EMPLOYEE", "MANAGER", "STUDENT", "FACULTY"];
const SUPPORTED_ROLES = Object.values(ROLES);
const BUSINESS_PROFILE_FIELDS = {
  department: "",
  employeeId: "",
  studentId: "",
  facultyId: "",
  managerId: "",
};

async function migrateLegacyRoles(logger = console) {
  const users = User.collection;
  const legacyRoleResult = await users.updateMany(
    {role: {$in: LEGACY_ROLES}},
    {
      $set: {role: ROLES.USER},
      $unset: BUSINESS_PROFILE_FIELDS,
    },
  );

  const unknownRoleResult = await users.updateMany(
    {
      $or: [
        {role: {$exists: false}},
        {role: null},
        {role: {$nin: SUPPORTED_ROLES}},
      ],
    },
    {
      $set: {role: ROLES.USER},
      $unset: BUSINESS_PROFILE_FIELDS,
    },
  );

  const profileCleanupResult = await users.updateMany(
    {
      $or: [
        {department: {$exists: true}},
        {employeeId: {$exists: true}},
        {studentId: {$exists: true}},
        {facultyId: {$exists: true}},
        {managerId: {$exists: true}},
      ],
    },
    {$unset: BUSINESS_PROFILE_FIELDS},
  );

  const migratedUsers = legacyRoleResult.modifiedCount + unknownRoleResult.modifiedCount;
  const cleanedProfiles = profileCleanupResult.modifiedCount;
  logger.log(
    `Role migration complete. Migrated users=${migratedUsers}, legacy-role users=${legacyRoleResult.modifiedCount}, unknown-role users=${unknownRoleResult.modifiedCount}, profile-cleanups=${cleanedProfiles}.`,
  );

  return {
    migratedUsers,
    legacyRoleUsers: legacyRoleResult.modifiedCount,
    unknownRoleUsers: unknownRoleResult.modifiedCount,
    profileCleanups: cleanedProfiles,
  };
}

module.exports = {
  LEGACY_ROLES,
  migrateLegacyRoles,
};
