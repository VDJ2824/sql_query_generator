function requireRoles(...allowedRoles) {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({message: "Authentication is required."});
    }
    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({message: "You are not authorized to perform this action."});
    }
    return next();
  };
}

module.exports = {
  requireRoles,
};
