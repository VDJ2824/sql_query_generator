# Secure AI-Based Natural Language to SQL Query Generator with Role-Based Access Control and Safe Query Execution

## 1. Abstract

This project is a secure AI-assisted system that converts natural language prompts into SQL query options and executes only validated, authorized, and security-enforced SQL. The final architecture is split into a React website, a Node.js + Express backend with MongoDB, and a Python FastAPI SQL intelligence service.

The system is designed around the principle that AI-generated SQL must never be trusted directly. SQL is validated before query options are returned, before preview, and again before execution. The application also enforces role-based access control, policy-based SQL restrictions, preview workflows, confirmation for write queries, query history, and audit logging.

## 2. Problem Statement

Natural-language-to-SQL tools make databases easier to use, but they can be dangerous if AI output is executed directly. Risks include unauthorized data access, SQL injection, unsafe UPDATE or DELETE queries, DDL/DCL misuse, transaction-control misuse, and leakage of credentials or private records.

This project solves the problem by separating the website, application security layer, and SQL intelligence layer. The frontend never makes trusted security decisions. Express verifies users and loads policies from MongoDB. The Python SQL service validates SQL, applies access-policy restrictions, previews impact, and safely executes only permitted SQL.

## 3. Project Objectives

- Provide a clean React website for users.
- Authenticate users using JWT and bcrypt password hashing.
- Store users, roles, policies, selected queries, history, and audit logs in MongoDB.
- Generate multiple SQL alternatives from natural language.
- Validate AI SQL with sqlglot.
- Enforce generic SQL access policies by database connection, schema, table, column, and operation.
- Support managed PostgreSQL and MySQL-compatible target databases.
- Prevent React from directly accessing the Python SQL service.
- Prevent users from accessing another user's private data.
- Require preview and confirmation for data-changing SQL.
- Audit all important actions.

## 4. Functional Requirements

- Users can register and log in.
- Express issues JWT access tokens.
- Authenticated users can view allowed database connections.
- Users can submit natural language prompts.
- The system returns up to three safe SQL alternatives.
- Users select one generated option by `optionId`.
- Express stores generated options and selected query records server-side.
- Preview shows estimated rows and safe preview rows.
- SELECT execution returns result rows.
- INSERT, UPDATE, and DELETE require preview and confirmation.
- TCL commands are view-only.
- DCL and dangerous database-administration DDL are blocked. Allow-listed table/index DDL requires preview and confirmation.
- Users can see only their own query history.
- Admins can view audit logs.

## 5. Non-Functional Requirements

- Security: Prevent unauthorized data access and unsafe SQL execution.
- Maintainability: Keep code modular across `client/`, `server/`, and `sql-service/`.
- Auditability: Record important events in MongoDB audit logs.
- Portability: Support local development through environment variables and managed cloud database URLs.
- Usability: Provide a clean website suitable for a college demonstration.
- Extensibility: Allow future target database connections through environment variables.

## 6. Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, React Router, Axios |
| Backend Gateway | Node.js, Express |
| Application Database | MongoDB, Mongoose |
| Authentication | JWT, bcrypt |
| SQL Service | Python FastAPI |
| SQL Toolkit | SQLAlchemy, sqlglot |
| AI Integration | Gemini API |
| Target Databases | Neon PostgreSQL, TiDB Cloud MySQL-compatible |
| Testing | Jest, Supertest, pytest, FastAPI TestClient |

## 7. System Architecture

The final architecture contains three active application services:

- `client/`: React website only.
- `server/`: Express + MongoDB security gateway.
- `sql-service/`: Python FastAPI SQL intelligence and execution service.

React calls only Express. Express verifies JWTs, loads users and policies from MongoDB, and calls the Python service using an internal API key. The Python service reads schemas, generates SQL, validates SQL, enforces access policies, previews impact, and safely executes against managed PostgreSQL or MySQL-compatible databases.

For the current cloud-first setup, MongoDB Atlas stores application data, Neon PostgreSQL is used as the PostgreSQL target engine, and TiDB Cloud is used as the MySQL-compatible target engine. Docker Compose files remain only as deprecated reference material.

The Mermaid architecture diagram is available in `docs/architecture.md`.

## 8. Module Description

### Authentication Module

Implemented in Express. It registers demo users, hashes passwords with bcrypt, verifies login credentials, and issues JWT tokens. Public registration creates a standard `USER` account and never allows role selection.

### Authorization and RBAC Module

Roles and access policies are stored in MongoDB. Express loads the authenticated user and active policies after JWT verification. React never provides trusted authorization data.

### Schema Reader Module

Implemented in `sql-service/`. It reads the selected target database schema dynamically using SQLAlchemy and filters tables/columns according to access policies from Express.

### AI SQL Generator Module

Implemented by `SqlGenerationService`. It sends allowed schema, dialect, role, access policy, and user prompt to Gemini when configured. If the AI API is unavailable, it uses safe fallback rules.

### SQL Validator Module

Implemented with sqlglot. It classifies SQL into SELECT, INSERT, UPDATE, DELETE, TCL, DCL, DDL, or UNKNOWN. It rejects multiple statements, comments, restricted schema access, unsafe structures, UPDATE/DELETE without WHERE, DCL, and dangerous DDL.

### Row-Level Security Module

The current general-purpose version does not depend on employee, student, manager, faculty, department, or other business-profile identity filters. Access is controlled through database connection grants, private SQL workspaces, and access policies that restrict schemas, tables, columns, and SQL operations.

### Query Alternatives Module

The generator returns different safe alternatives, such as detailed rows, selected columns, and aggregate summaries. Express stores generated options temporarily in MongoDB.

### Query Impact Analyzer Module

Preview is handled by `sql-service/`. SELECT previews return count and up to 20 rows. UPDATE and DELETE previews show affected rows without modifying data. INSERT preview validates intended impact without inserting.

### Safe Execution Module

Execution is handled by `sql-service/`. It revalidates, rechecks policy, reenforces row-level security, requires confirmation for writes and DDL, blocks TCL/DCL/dangerous DDL, and executes only allowed SQL.

### Query History and Audit Log Module

Express stores query history and audit logs in MongoDB. Users can see only their own history. Admin users can view audit logs.

## 9. Database Design

MongoDB collections:

- `users`: username, email, passwordHash, role, active, private workspace metadata, createdAt.
- `database_connections`: connectionName, databaseType, credentialEnvironmentVariableName, allowedRoles, active.
- `access_policies`: role, databaseConnectionId, allowedOperations, allowedSchemas, allowedTables, blockedTables, allowedColumns, requiresPreviewFor, requiresConfirmationFor, active.
- `generated_query_options`: temporary generated options per user.
- `selected_queries`: one active selected query per user, expiring after 15 minutes.
- `query_history`: per-user execution records.
- `audit_logs`: security and workflow audit events.

Target relational databases are external to MongoDB and currently use managed PostgreSQL and MySQL-compatible engines. Each user receives one private SQL workspace per engine. TiDB uses one database per user. PostgreSQL uses one database per user when supported, otherwise one schema per user.

## 10. User Roles and Permissions

| Role | Data Access |
| --- | --- |
| ADMIN | Manages users, database connections, access policies, and audit logs |
| USER | Uses only database connections and SQL operations explicitly granted to USER |

## 11. SQL Command Execution Policy

| Command | Policy |
| --- | --- |
| SELECT | Allowed after validation, authorization, and row-level enforcement |
| INSERT | Requires policy permission, preview, and confirmation |
| UPDATE | Requires WHERE, policy permission, preview, row estimate, row-level enforcement, and confirmation |
| DELETE | Requires WHERE, policy permission, preview, row estimate, row-level enforcement, and confirmation |
| TCL | View-only, never executed |
| DCL | Blocked |
| Table/Index DDL | Allowed only by policy after preview and confirmation |
| Dangerous DDL | Blocked |
| UNKNOWN | Blocked |

## 12. API Endpoints

Express public API:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/database-connections`
- `POST /api/database-connections`
- `POST /api/queries/generate`
- `POST /api/queries/select`
- `POST /api/queries/preview`
- `POST /api/queries/execute`
- `GET /api/history`
- `GET /api/admin/audit-logs`

Internal Python API:

- `GET /health`
- `POST /internal/schema`
- `POST /internal/generate`
- `POST /internal/preview`
- `POST /internal/execute`

## 13. Security Features

- React never calls Python directly.
- Express never trusts role, policy, allowed tables, allowed columns, or SQL from React.
- SQL service requires internal API key.
- AI-generated SQL is validated before use.
- Row-level security is enforced before preview and execution.
- Multiple statements and SQL comments are blocked.
- DCL and dangerous DDL are blocked.
- TCL is view-only.
- UPDATE and DELETE require WHERE.
- Writes require preview and confirmation.
- Password hashes and secrets are not returned to React.
- Audit logs are admin-only.
- PostgreSQL and MySQL are private in production and are not exposed publicly.
- Normal target database queries use restricted database accounts.
- Separate privileged admin database connections are available only for allow-listed infrastructure actions such as `CREATE DATABASE`.
- Unsafe infrastructure commands such as `DROP DATABASE`, `CREATE ROLE`, `ALTER SYSTEM`, `GRANT`, and `REVOKE` are blocked.

## 14. Test Cases

Implemented tests cover:

- Valid login and JWT verification.
- Role-protected database connection creation.
- User-owned query history.
- Express-to-sql-service integration with mocked Python responses.
- Server-side query option storage and selection.
- Preview-before-write enforcement.
- SQL classification and validation.
- Generic policy enforcement for allowed tables, blocked tables, columns, and operations.
- TCL view-only behavior.
- DDL/DCL blocking.
- Manager update after confirmation.
- Employee update blocking.

## 15. Sample Inputs and Outputs

Sample prompt:

```text
Show sales by region
```

Sample generated option:

```json
{
  "optionId": 1,
  "title": "Sales by region",
  "generatedSql": "SELECT region, amount FROM sales",
  "finalEnforcedSql": "SELECT region, amount FROM sales",
  "queryType": "SELECT",
  "executionAllowed": true,
  "requiresConfirmation": false
}
```

## 16. Limitations

- JWT is stored in `sessionStorage` for demo simplicity.
- Public registration creates only a standard USER account.
- Complex joins, unions, CTEs, and nested queries are blocked.
- No rate limiting is implemented yet.
- PostgreSQL database-per-user depends on cloud credential privileges. If unavailable, the application uses a private schema-per-user fallback.
- SQLite private file workspaces are reserved for future local/offline expansion.
- Demo users have simple passwords.

## 17. Future Enhancements

- Admin-only user management UI.
- Rate limiting and account lockout.
- Production deployment with HTTPS and automated backup retention.
- More advanced SQL planning for safe joins.
- Database migration tooling.
- More detailed audit dashboards.

## 18. Conclusion

This project demonstrates a secure approach to AI-assisted SQL generation. By separating the React website, Express security gateway, MongoDB policy store, and Python SQL intelligence service, the system avoids trusting the frontend or AI output directly. Validation, authorization, row-level enforcement, preview, confirmation, execution, history, and audit logging work together to reduce the risk of unsafe database access.
