# Security Controls

This project is designed as a secure, beginner-friendly demonstration of AI-assisted SQL generation. The most important principle is that generated SQL is never trusted just because it came from the AI or the frontend.

## Trust Boundary

- The Gemini response is treated as untrusted input.
- Frontend-submitted SQL is not trusted.
- Query options are stored server-side after generation.
- `/select-query` uses the server-saved generated option instead of trusting the SQL sent by the browser.
- SQL is validated and authorized before preview.
- SQL is validated and authorized again before execution.

## Authentication

- Passwords are hashed with bcrypt through Passlib.
- Plaintext passwords are never stored.
- API routes use JWT bearer tokens with `OAuth2PasswordBearer`.
- Token settings come from environment variables:
  - `SECRET_KEY`
  - `ALGORITHM`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`
- Protected routes return `401` for missing, invalid, or expired tokens.
- Password hashes are not returned in API responses.

## Authorization

Supported roles:

- admin
- manager
- employee
- faculty
- student

Controls:

- Admin can access allowed Employee and Students data.
- Manager access is limited to Employee rows in the manager's department.
- Employee access is limited to the employee's own Employee row.
- Faculty access is limited to Students assigned to that faculty user.
- Student access is limited to the student's own Students row.
- Restricted internal tables are blocked from normal schema and SQL access.
- Restricted columns such as `password_hash` are blocked.

## SQL Validation

SQL validation is implemented with sqlglot in `backend/sql_validator.py`.

Blocked or restricted behavior:

- Multiple SQL statements
- Semicolon-separated statement chains
- SQL comments used to bypass validation
- Unknown query types
- Restricted tables
- Restricted columns
- Unsafe JOIN and UNION patterns in this starter project
- UPDATE without WHERE
- DELETE without WHERE

Query type policy:

- SELECT can execute after validation and authorization.
- INSERT is admin-only and requires confirmation.
- UPDATE is admin or authorized-manager only, requires WHERE, preview, and confirmation.
- DELETE is admin-only, requires WHERE, preview, and confirmation.
- TCL commands are view-only and never executed.
- DCL commands are blocked.
- Dangerous DDL commands are blocked.

## Row-Level Security

Row-level security is enforced server-side in `backend/impact_analyzer.py`.

Examples:

- Employee queries receive an `employee_id = current_user.employee_id` filter.
- Student queries receive a `student_id = current_user.student_id` filter.
- Manager queries receive a `department = current_user.department` filter.
- Faculty queries receive a `faculty_id = current_user.user_id` filter.
- Existing WHERE clauses are combined with the enforced rule instead of replaced.

## Preview and Execution Safety

- Preview never executes UPDATE, DELETE, TCL, DCL, or DDL.
- SELECT preview returns a count and up to 20 rows.
- UPDATE preview converts the write query into a SELECT preview using the same enforced WHERE condition.
- DELETE preview converts the delete query into a SELECT preview using the same enforced WHERE condition.
- Execution re-runs validation, authorization, and row-level enforcement.
- SELECT execution returns up to 100 rows.
- UPDATE and DELETE must have a successful preview audit event and explicit confirmation.
- Write failures trigger database rollback handling.

## Audit Logging

Important actions are audited:

- Login success and failure
- Schema access
- Query generation
- Query selection
- Validation failure
- Authorization failure
- Preview
- Execution attempt
- Successful execution
- Blocked TCL, DCL, and DDL commands
- Suspicious SQL attempts

The audit logger does not store passwords, JWT tokens, or credentials intentionally. It also redacts common password, token, secret, API key, and bearer-token patterns before persisting audit text fields.

## Frontend Security Behavior

- Protected sections are disabled before login.
- JWT tokens are sent in the `Authorization: Bearer <token>` header.
- `401` responses clear the token and return the user to the login state.
- `403` responses display the backend authorization message.
- Displayed backend text is escaped to reduce HTML injection risk.
- Buttons are hidden or disabled based on backend responses for user experience only.
- Real authorization is enforced by the backend.

## Known Demo Limitations

- SQLite is used for development, not production deployment.
- JWTs are stored in `sessionStorage` for the demo frontend.
- Demo users use simple passwords to make college-project testing easy.
- Registration is temporarily open for testing; production registration should be admin-only.
- CORS is permissive for local development and should be restricted for deployment.
- The default development `SECRET_KEY` must be replaced before deployment.

## Production Hardening Checklist

- Replace demo passwords and rotate seeded credentials.
- Use a strong random `SECRET_KEY`.
- Serve the frontend and backend over HTTPS.
- Restrict CORS origins.
- Use a production database with migrations.
- Add rate limiting for login and generation endpoints.
- Add stronger audit retention and monitoring.
- Consider secure HTTP-only cookies for token storage.
- Review row-level security rules before allowing complex joins.
