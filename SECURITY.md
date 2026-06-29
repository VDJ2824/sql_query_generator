# Security Controls

This project follows a defense-in-depth design for AI-assisted SQL. The core rule is: AI-generated SQL is never trusted directly.

## Architecture Security Boundary

- `client/` is a React website only.
- React calls only the Express API at `/api`.
- React never calls `sql-service/` directly.
- `server/` is the trusted gateway between the website, MongoDB Atlas, and `sql-service/`.
- `sql-service/` is internal and requires `x-internal-api-key` for every `/internal/*` endpoint.
- Neon PostgreSQL and TiDB Cloud connection URLs live only in SQL service environment variables.
- MongoDB, target database, Gemini, JWT, and internal API secrets are never exposed to React.

## Managed Cloud Database Model

The normal workflow uses:

- MongoDB Atlas through `MONGODB_URI`.
- Neon PostgreSQL through `POSTGRES_DEMO_URL`.
- TiDB Cloud MySQL-compatible through `MYSQL_DEMO_URL`.

Each user receives one private SQL workspace per cloud SQL engine. TiDB uses one private database per user. PostgreSQL uses a private database when the credential supports `CREATE DATABASE`; otherwise the SQL service provisions one private schema per user and forces PostgreSQL sessions into that schema.

Docker compose files remain for reference, but Docker-managed databases are deprecated for the normal setup.

## Secrets

The following values must not be exposed to React:

- `MONGODB_URI`
- `JWT_SECRET`
- `SQL_SERVICE_URL`
- `SQL_SERVICE_API_KEY`
- `GEMINI_API_KEY`
- `POSTGRES_DEMO_URL`
- `MYSQL_DEMO_URL`
- Any target database password or connection string

Environment examples contain placeholders only.

## Authentication

- Express handles login and JWT issuance.
- Passwords are hashed with bcrypt before storage.
- Password hashes are excluded from normal user responses.
- Protected Express endpoints use JWT bearer authentication.
- Public registration accepts username, email, password, and confirmPassword only.
- Public registration always creates a `USER` account.
- `/api/auth/me` loads the current user from MongoDB so stale token role data is not trusted.

## Authorization

- Supported roles are `USER` and `ADMIN`.
- Roles and policies are stored in MongoDB.
- Express loads the current user from MongoDB after JWT verification.
- Express loads active database connection metadata and access policies from MongoDB.
- React-submitted roles, policies, allowed tables, allowed columns, user IDs, and SQL are not trusted.
- User history and selected queries are scoped by authenticated `userId`.
- Generated and selected SQL options are also bound to the authenticated user's private workspace identifier.
- Audit logs are protected by admin-only middleware.

## SQL Service Controls

`sql-service/` performs:

- Dynamic schema reading.
- SQL dialect selection for PostgreSQL and MySQL-compatible engines.
- SQL generation with Gemini plus safe fallback rules.
- SQL classification and validation with sqlglot.
- Policy enforcement by database connection, table, column, and operation.
- Lazy private workspace provisioning and workspace-scoped SQLAlchemy engines.
- Safe preview.
- Safe execution.

The service validates SQL:

- before returning generated options
- before preview
- before execution

Generation may fall back to access-policy schema metadata when the target database is unreachable. If the SQL service itself is unavailable, Express can return minimal policy-based SELECT suggestions so the prompt workflow does not freeze. These fallbacks are used only for suggesting SQL options. Preview and execution still require Python SQL-service validation and fail closed if the SQL service or target database is unavailable.

## SQL Command Policy

| SQL Type | Policy |
| --- | --- |
| DQL | `SELECT` can execute after schema and policy validation |
| DML | `INSERT`, `UPDATE`, and `DELETE` can execute only when allowed by policy |
| DDL | Allow-listed table/index DDL can execute only when policy allows `DDL`, after preview and confirmation |
| TCL | Explanation-only; never sent to the target database |
| DCL | Blocked |
| Database administration | Blocked, including database/user/role/system commands |
| UNKNOWN | Blocked |

CRUD in this project means `SELECT`, `INSERT`, `UPDATE`, and `DELETE`. `DROP TABLE` has a stronger confirmation requirement than `DELETE`: the user must type the exact table name, and Express verifies that typed value server-side before execution.

Blocked patterns include:

- Multiple SQL statements
- SQL comments used to bypass checks
- Unsupported dialect syntax
- Restricted tables
- Restricted columns
- Cross-schema or cross-database references
- `SELECT *` when column restrictions are active
- `UPDATE` without `WHERE`
- `DELETE` without `WHERE`
- Unsafe joins, unions, CTEs, nested selects, and stored-procedure style commands

## Access Policy Enforcement

The general-purpose version does not use employee, student, faculty, manager, department, or other business-profile identity filters.

Access is controlled by:

- database connection grants by role
- allowed operations
- allowed schemas
- allowed tables
- blocked tables
- allowed columns
- preview and confirmation rules

## Preview And Execution

- Express stores generated options server-side.
- Users select by `optionId` only.
- Express retrieves the selected option from MongoDB.
- Express never accepts arbitrary SQL from React for preview or execution.
- Selected queries expire after 15 minutes.
- A user can have only one active selected query.
- Selected queries must match the authenticated user's current workspace before preview or execution.
- `INSERT`, `UPDATE`, and `DELETE` are blocked by Express until preview has happened.
- `UPDATE` and `DELETE` must include `WHERE`.
- Writes require confirmation when policy marks them as confirmation-required.
- `sql-service/` revalidates and rechecks policy before execution.
- Every execution attempt, including blocked attempts, is stored in history and audit logs.

## Audit Logging

Audited events include:

- Register
- Login success/failure
- Database connection metadata creation
- Query generation
- Query selection
- Preview
- Execution success
- Execution blocked
- Deprecated unsafe route usage

Audit text fields are redacted for common password, token, secret, API key, and bearer-token patterns.

## Remaining Limitations

- JWT is stored in `sessionStorage` for demo simplicity. Production should consider secure, HTTP-only cookies.
- Public registration is available for demonstration and always creates a standard `USER` account.
- No rate limiting is implemented yet.
- No production-grade migration system is included.
- Complex joins/unions/CTEs are blocked instead of partially supported.
- PostgreSQL database-per-user depends on provider credential privileges. When unavailable, the secure fallback is schema-per-user.
- SQLite private file workspaces are reserved for local/offline expansion; the active cloud workflow focuses on Neon PostgreSQL and TiDB Cloud.
- Demo users use simple passwords and should not be used in production.
