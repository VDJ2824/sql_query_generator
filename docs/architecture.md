# Architecture

## Current Managed Cloud Architecture

```mermaid
flowchart LR
  User[User Browser] --> Client[client/<br/>React + Vite website]
  Client -->|HTTPS /api only<br/>JWT bearer token| Server[server/<br/>Node.js + Express gateway]
  Server -->|Mongoose + TLS| Mongo[(MongoDB Atlas<br/>users, roles, policies,<br/>selected queries, history,<br/>audit logs)]
  Server -->|x-internal-api-key<br/>verified user context + policies| SqlService[sql-service/<br/>Python FastAPI SQL intelligence]
  SqlService -->|Gemini API key from service env only| Gemini[Gemini API]
  SqlService -->|SQLAlchemy + TLS<br/>private DB or schema<br/>validated SQL only| Neon[(Neon PostgreSQL)]
  SqlService -->|SQLAlchemy + TLS<br/>private database<br/>validated SQL only| TiDB[(TiDB Cloud<br/>MySQL-compatible)]

  Client -. forbidden .-> SqlService
  Client -. no secrets .-> Neon
  Client -. no secrets .-> TiDB
  Server -. no target DB SQL execution .-> Neon
  Server -. no target DB SQL execution .-> TiDB
```

## Deprecated Docker VPS Reference

```mermaid
flowchart TB
  Internet[Internet] -->|80 / 443 only| Nginx[client container<br/>Nginx serving React]
  Nginx -->|/api internal proxy| Express[server container<br/>Express API]
  Express -->|Mongoose| Mongo[(MongoDB<br/>container or Atlas)]
  Express -->|x-internal-api-key| FastAPI[sql-service container<br/>FastAPI]
  FastAPI -->|restricted POSTGRES_APP_URL| Postgres[(PostgreSQL container<br/>named volume)]
  FastAPI -->|restricted MYSQL_APP_URL| MySQL[(MySQL container<br/>named volume)]
  Backup[backup scripts] --> Postgres
  Backup --> MySQL

  Internet -. blocked .-> Express
  Internet -. blocked .-> FastAPI
  Internet -. blocked .-> Postgres
  Internet -. blocked .-> MySQL
  Internet -. blocked .-> Mongo
```

This Docker VPS diagram is retained as a deprecated reference for older deployment experiments. The current preferred deployment uses managed MongoDB Atlas, Neon PostgreSQL, and TiDB Cloud rather than Docker-managed databases.

## Responsibilities

### client/

- React website only.
- Calls only the Express API base URL configured by `VITE_API_BASE_URL`.
- Stores JWT in `sessionStorage` for this college demo.
- Displays generated SQL, security-enforced SQL, preview, execution result, history, and audit UI.
- Does not call `sql-service/`.
- Does not contain MongoDB URLs, target database URLs, Gemini keys, or internal service keys.
- Does not make trusted authorization decisions.

### server/

- Node.js + Express gateway.
- MongoDB + Mongoose persistence.
- JWT authentication and bcrypt password hashing.
- Stores users, roles, database connection metadata, access policies, generated options, selected queries, query history, and audit logs.
- Builds trusted verified user context from MongoDB after JWT verification.
- Generates and stores private SQL workspace metadata for each user.
- Calls `sql-service/` using `x-internal-api-key`.
- Never exposes `SQL_SERVICE_URL`, `SQL_SERVICE_API_KEY`, MongoDB secrets, Gemini keys, or target database credentials to React.
- Never accepts arbitrary SQL from React for preview or execution.

### sql-service/

- Python FastAPI internal service.
- Requires `x-internal-api-key` for `/internal/*`.
- Reads target database schema dynamically with SQLAlchemy.
- Lazily provisions one private workspace per user per cloud SQL engine.
- TiDB uses a private database per user.
- PostgreSQL uses a private database per user when `CREATEDB` is available, otherwise a private schema per user.
- Performs AI/NLP SQL generation with Gemini when configured.
- Performs SQL parsing, classification, validation, dialect handling, row-level enforcement, preview, and safe execution.
- Supports PostgreSQL and MySQL-compatible target databases through environment variables.
- Revalidates and reenforces row-level security before preview and again before execution.
- Uses managed database URLs configured only in the SQL service environment.
- Blocks database administration commands such as `CREATE DATABASE`, `DROP DATABASE`, `CREATE USER`, `GRANT`, and `ALTER SYSTEM`.

## Query Workflow

```mermaid
sequenceDiagram
  participant C as React client
  participant E as Express server
  participant M as MongoDB
  participant S as Python sql-service
  participant D as Target RDBMS

  C->>E: POST /api/queries/generate(prompt, databaseConnectionId)
  E->>M: Load user, active connection, access policies
  E->>S: /internal/generate with verified context + workspace metadata
  S->>D: Provision workspace if needed
  S->>D: Read schema only from user's workspace
  S->>S: Generate, validate, enforce, deduplicate options
  S-->>E: Safe query options
  E->>M: Store generated options temporarily
  E-->>C: Query options

  C->>E: POST /api/queries/select(optionId)
  E->>M: Retrieve stored option for current user
  E->>M: Replace active selected query
  E-->>C: Selected query metadata

  C->>E: POST /api/queries/preview
  E->>M: Retrieve selected query
  E->>S: /internal/preview with stored SQL and verified workspace
  S->>S: Revalidate and enforce workspace isolation
  S->>D: SELECT preview/count only when safe
  S-->>E: Preview response
  E->>M: Audit preview and update selected query preview state
  E-->>C: Preview response

  C->>E: POST /api/queries/execute(confirmed)
  E->>M: Retrieve selected query
  E->>S: /internal/execute with stored SQL and verified workspace
  S->>S: Revalidate, recheck policy, reenforce workspace isolation
  S->>D: Execute only allowed SQL
  S-->>E: Execution response
  E->>M: Save history and audit log
  E-->>C: Execution response
```

## Data Stores

- MongoDB stores application/security data only.
- Target relational databases store business data queried by SQL.
- Express stores only target database credential environment variable names, never raw target database passwords.
- The Python service reads the actual target database URL from its own environment.

## Security Boundaries

- React cannot call `sql-service/`.
- React cannot provide trusted role, allowed tables, columns, policies, or executable SQL.
- Express is the only caller of `sql-service/`.
- `sql-service/` treats AI SQL as untrusted and validates before returning options, before preview, and before execution.
- TCL is view-only.
- DCL and dangerous DDL are blocked.
- `DROP DATABASE`, `CREATE ROLE`, `ALTER SYSTEM`, `GRANT`, `REVOKE`, and unsafe infrastructure commands are blocked.
