# Secure AI SQL Query Generator

A college-project SQL assistant that converts natural-language prompts into SQL options, validates them, previews impact, and executes only backend-approved queries.

The central rule is simple: AI-generated SQL is never trusted directly. SQL is validated before generation output is stored, again before preview, and again before execution.

## Active Architecture

- `client/`: React + Vite website only.
- `server/`: Node.js + Express gateway, MongoDB Atlas metadata, JWT authentication, users, policies, selected queries, history, and audit logs.
- `sql-service/`: Python FastAPI internal service for schema reading, Gemini-based SQL generation, sqlglot validation, preview, and safe execution.
- `docs/`: architecture, API, migration, cloud-refactor, and deployment notes.
- `legacy/`: older implementations retained for reference.

React calls only Express at `/api`. Express is the only service that may call `sql-service`. Database credentials, MongoDB secrets, Gemini keys, and internal service keys must never be exposed to React.

## Service Boundary

The active request path is:

```text
React/Vite browser
  -> Express API
  -> FastAPI SQL service
  -> Neon PostgreSQL or TiDB/MySQL target workspace
```

Responsibilities are intentionally separated:

- React stores only the JWT for this college-project demo and calls the Express `/api` base URL. It never calls FastAPI directly.
- Express owns MongoDB Atlas access, JWT authentication, users, workspace mapping, database connection metadata, access policies, generated options, selected queries, query history, and audit logs.
- Express calls FastAPI with `SQL_SERVICE_URL` and the `x-internal-api-key` header.
- FastAPI does not connect to MongoDB in the active application flow. It performs schema inspection, Gemini SQL generation, SQL validation, preview, execution, and PostgreSQL/MySQL workspace routing.
- React never receives MongoDB URIs, target database URLs, provider credentials, `SQL_SERVICE_API_KEY`, internal workspace identifiers, or private schema/database names.

## Managed Cloud Database Direction

The normal development and deployment path now uses managed cloud databases:

- MongoDB Atlas through `MONGODB_URI` for authentication, policies, history, selected queries, and audit logs.
- Neon PostgreSQL through `POSTGRES_DEMO_URL` as a target SQL engine.
- TiDB Cloud MySQL-compatible through `MYSQL_DEMO_URL` as a target SQL engine.

Docker compose files remain in the repository for reference and older local experiments, but Docker-managed PostgreSQL/MySQL/MongoDB are deprecated for the normal workflow.

Each application user receives a private SQL workspace per cloud SQL engine. TiDB uses one private database per user. PostgreSQL uses one private database when the provider credential supports it; otherwise it safely falls back to one private schema per user inside the configured Neon database. Users do not need Neon accounts, TiDB accounts, or external account linking.

## Technology Stack

- Client: React, Vite, React Router, Axios, CSS.
- Server: Node.js, Express, MongoDB, Mongoose, JWT, bcrypt.
- SQL service: Python 3, FastAPI, SQLAlchemy, sqlglot, Gemini API.
- Target SQL engines: PostgreSQL and MySQL-compatible databases.
- Tests: Jest/Supertest for Express, pytest for sql-service, Vitest for React.

## Environment Setup

Create the root cloud environment file from the example:

```bash
cp .env.cloud.example .env.cloud
```

Fill these root `.env.cloud` values with your cloud credentials:

```env
MONGODB_URI=
JWT_SECRET=
JWT_EXPIRES_IN=1h
SQL_SERVICE_URL=http://127.0.0.1:8001
SQL_SERVICE_API_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
POSTGRES_DEMO_URL=
MYSQL_DEMO_URL=
MYSQL_SSL_CA_PATH=
VITE_API_BASE_URL=http://127.0.0.1:5000/api
```

For local non-Docker development, both `server/` and `sql-service/` automatically load the root `.env.cloud` file. Existing platform environment variables still win over file values, so this also works safely on Render, Railway, Vercel, or similar platforms where variables are injected directly.

Do not copy database URLs, MongoDB credentials, Gemini keys, JWT secrets, or internal service keys into `client/.env`. The React client must only know the public Express API URL, for example:

```env
VITE_API_BASE_URL=http://127.0.0.1:5000/api
```

## Deployment Environment Variables

Vercel client:

```env
VITE_API_BASE_URL=
```

Render Express server:

```env
MONGODB_URI=
JWT_SECRET=
JWT_EXPIRES_IN=1h
SQL_SERVICE_URL=
SQL_SERVICE_API_KEY=
CLIENT_URL=
NODE_ENV=production
```

Optional Express email OTP variables:

```env
BREVO_API_KEY=
BREVO_FROM=
LOGIN_OTP_EXPIRES_IN_MINUTES=10
EMAIL_SEND_TIMEOUT_MS=10000
```

Render FastAPI SQL service:

```env
SQL_SERVICE_API_KEY=
POSTGRES_DEMO_URL=
MYSQL_DEMO_URL=
MYSQL_SSL_CA_PATH=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

Do not configure `MONGODB_URI` on the FastAPI SQL service. MongoDB access belongs only to Express.

`POSTGRES_DEMO_URL` must be a SQLAlchemy PostgreSQL URL, for example:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

`MYSQL_DEMO_URL` must be a SQLAlchemy MySQL-compatible URL, for example:

```text
mysql+pymysql://USER:PASSWORD@HOST:4000/DATABASE?ssl_verify_cert=true
```

Use the exact SSL/TLS parameters required by your Neon or TiDB Cloud dashboard. If your TiDB runtime needs a separate CA bundle path, set `MYSQL_SSL_CA_PATH`; do not place certificate contents in React or logs.

## Initialize Cloud Demo Tables

After setting `POSTGRES_DEMO_URL` and `MYSQL_DEMO_URL`, create the sample tables and data:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r sql-service/requirements.txt
cd sql-service
python3 scripts/init_cloud_databases.py --target all
```

This creates idempotent demo tables:

- `Employee`
- `Students`
- `Department`

Each managed engine receives 25 employees, 25 students, and 5 departments.

## Run Locally Without Docker

Terminal 1, start the Python SQL service:

```bash
cd sql-service
source ../.venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Terminal 2, start the Express server:

```bash
cd server
npm install
npm run seed
npm run backfill:workspaces
npm run dev
```

Terminal 3, start the React client:

```bash
cd client
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Seeded users:

```text
admin@example.com / admin123
demo.user@example.com / user123
```

## Query Workflow

1. Log in through Express.
2. Choose an allowed managed database connection.
3. Submit a natural-language prompt.
4. Express calls the Python SQL service with verified user, policy, and connection context.
5. The SQL service lazily provisions the user's private workspace for the selected engine.
6. SQL options are stored server-side and tied to the authenticated user, selected database, dialect, workspace, expiry, and execution state.
7. React selects an option by `optionId` only.
8. Preview revalidates SQL and estimates impact inside that user's workspace.
9. Execution revalidates SQL again inside the same workspace and logs the attempt.

If the selected target database is temporarily unreachable during generation, the SQL service can still generate conservative options from MongoDB access policies. If the SQL service itself is unavailable, Express returns a minimal policy-based SELECT fallback instead of blocking the prompt workflow. Preview and execution still require Python SQL-service validation and a successful target database connection.

## SQL Security Rules

- CRUD means `SELECT`, `INSERT`, `UPDATE`, and `DELETE`.
- DQL `SELECT` can execute after policy validation.
- DML `INSERT`, `UPDATE`, and `DELETE` can execute only when allowed by policy.
- `UPDATE` and `DELETE` require `WHERE`, preview, affected-row estimate, and confirmation.
- `DELETE` warns that deleted rows cannot be restored through the application.
- TCL commands are explanation-only and never sent to the database driver.
- DCL commands such as `GRANT` and `REVOKE` are blocked.
- Database administration commands such as `CREATE DATABASE`, `DROP DATABASE`, `CREATE SCHEMA`, `DROP SCHEMA`, `CREATE USER`, `CREATE ROLE`, `GRANT`, `REVOKE`, and `ALTER SYSTEM` are blocked for normal user SQL.
- Allow-listed table/index DDL such as `CREATE TABLE` can run only when policy allows `DDL`, after preview and explicit confirmation.
- `DROP TABLE` requires a stronger confirmation: the user must type the exact table name, and the server verifies it before execution.
- Multiple statements, SQL comments, restricted tables, system schemas, and cross-database/cross-schema references are blocked.
- Users may create multiple ordinary tables inside their own private workspace. They cannot reference another user's PostgreSQL schema, TiDB database, or schema-qualified/database-qualified object names.

## Main API Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login` - verifies email/password and sends a Brevo OTP challenge
- `POST /api/auth/verify-login-otp` - verifies the one-time code and returns the JWT
- `GET /api/auth/me`
- `GET /api/database-connections`
- `POST /api/database-connections`
- `POST /api/queries/generate`
- `POST /api/queries/select`
- `POST /api/queries/preview`
- `POST /api/queries/execute`
- `GET /api/history`
- `GET /api/admin/audit-logs`
- `GET /health` on `sql-service`
- `POST /internal/schema` on `sql-service`, internal only
- `POST /internal/generate` on `sql-service`, internal only
- `POST /internal/preview` on `sql-service`, internal only
- `POST /internal/execute` on `sql-service`, internal only

## Brevo Login OTP

Login is a two-step flow:

1. The user submits `username` and `password` to `POST /api/auth/login`.
2. Express verifies credentials from MongoDB, stores a hashed one-time code, and sends the code using Brevo when configured.
3. The user submits the OTP to `POST /api/auth/verify-login-otp`.
4. Express verifies the OTP, clears it from the user record, and returns the JWT.

Backend-only environment variables:

```bash
BREVO_API_KEY=
BREVO_FROM=
LOGIN_OTP_EXPIRES_IN_MINUTES=10
EMAIL_SEND_TIMEOUT_MS=10000
```

Do not add Brevo keys to `client/.env`. In non-production local development, the backend may return `debugOtp` if Brevo is not configured so the app remains testable.

## Tests

Run Express tests:

```bash
cd server
npm test
```

Run sql-service tests:

```bash
cd sql-service
source ../.venv/bin/activate
python3 -m pytest -q
```

Run React checks:

```bash
cd client
npm test
npm run build
```

## Notes

- `docker-compose.yml` and `docker-compose.production.yml` are retained for reference but are not the preferred cloud workflow.
- `GEMINI_API_KEY` is the active AI provider key in this version.
- `OPENAI_API_KEY` and `OPENAI_MODEL` appear only as optional placeholders for a future provider switch.
- See `SECURITY.md` for the security model.
- See `docs/cloud-refactor-plan.md` for the cloud migration plan.
- See `docs/workspace-isolation.md` for private SQL workspace isolation details.
