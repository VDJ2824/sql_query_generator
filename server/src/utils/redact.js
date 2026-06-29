const SECRET_PATTERNS = [
  /\b(password|token|secret|api[_-]?key)\b\s*[:=]\s*['"]?[^'"\s,;}]+/gi,
  /\bBearer\s+[A-Za-z0-9._~+/-]+=*/gi,
  /mongodb(\+srv)?:\/\/[^\s]+/gi,
  /(postgres|postgresql|mysql|sqlite):\/\/[^\s]+/gi,
];

function redactSensitiveText(value = "") {
  let redacted = String(value || "");
  redacted = redacted.replace(SECRET_PATTERNS[0], "$1=[REDACTED]");
  redacted = redacted.replace(SECRET_PATTERNS[1], "Bearer [REDACTED]");
  redacted = redacted.replace(SECRET_PATTERNS[2], "mongodb://[REDACTED]");
  redacted = redacted.replace(SECRET_PATTERNS[3], "$1://[REDACTED]");
  return redacted;
}

module.exports = {
  redactSensitiveText,
};
