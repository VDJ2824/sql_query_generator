# Private SQL Workspace Isolation

## Goal

Each AI SQL Query Generator account receives one private workspace per supported cloud SQL engine:

- PostgreSQL / Neon: one private database when supported, otherwise one private schema inside the configured database.
- TiDB / MySQL-compatible: one private database.

Users can create multiple tables inside their own workspace, but they must never inspect, preview, execute, create, alter, or drop objects in another user's workspace.

## Naming

Workspace identifiers are generated only by the backend:

```text
user_<sanitized_username>_<mongodb_id_suffix>
```

Rules:

- lowercase only
- letters, digits, and underscores only
- username is sanitized before use
- immutable MongoDB ObjectId suffix prevents collisions
- React never sends, edits, or displays the workspace name

## Current Flow To Preserve

1. React sends login, selected database connection, prompt, option ID, and confirmation payloads only to Express.
2. Express verifies JWT, loads the current user from MongoDB, loads database connection metadata, loads access policies, and calls FastAPI.
3. FastAPI reads schema, generates SQL, validates SQL, previews SQL, and executes SQL against the selected relational engine.
4. Express stores generated options, selected queries, query history, and audit logs in MongoDB.

## Target Flow

1. On registration, Express stores workspace metadata on the MongoDB user document.
2. Existing users are backfilled by a script without changing passwords, history, audit logs, or selected query ownership.
3. Workspaces are lazily provisioned:
   - first PostgreSQL selection provisions the user's PostgreSQL workspace
   - first TiDB selection provisions the user's TiDB workspace
4. Express sends verified user context, including workspace identifier and engine-specific workspace name, only to FastAPI.
5. FastAPI provisions the workspace idempotently and creates a workspace-scoped SQLAlchemy engine.
6. Schema inspection, generation, preview, and execution all use that workspace-scoped engine.

## PostgreSQL Strategy

FastAPI performs a safe capability check using metadata/privilege reads only. It does not create or modify a real database during the check.

If `CREATE DATABASE` is available:

- create a private PostgreSQL database for the user
- connect directly to that database for all PostgreSQL actions

If unavailable:

- create a private schema using `CREATE SCHEMA IF NOT EXISTS <workspace>`
- force the session search path into the private schema
- inspect only that schema
- reject schema-qualified and database-qualified user SQL

## TiDB Strategy

FastAPI uses the trusted TiDB base URL as the provisioner connection and creates:

```sql
CREATE DATABASE IF NOT EXISTS <workspace>;
```

Then it builds a workspace-specific SQLAlchemy URL using SQLAlchemy URL manipulation utilities, not string replacement.

## Blocked Commands

Normal users can never execute:

- `CREATE DATABASE`
- `DROP DATABASE`
- `CREATE SCHEMA`
- `DROP SCHEMA`
- `CREATE USER`
- `DROP USER`
- `ALTER USER`
- `CREATE ROLE`
- `DROP ROLE`
- `GRANT`
- `REVOKE`
- `ALTER SYSTEM`
- `FLUSH`
- `SHUTDOWN`
- `USE database_name`
- cross-schema or cross-database references
- SQL comments
- multiple SQL statements

TCL commands remain explanation-only and are never sent to the database driver.

## Verification

Tests should prove:

- workspace names are deterministic, sanitized, and collision-safe
- existing users can be backfilled safely
- TiDB provisioning is idempotent
- PostgreSQL chooses database-per-user or schema-per-user safely
- schema inspection only sees the current user's workspace
- generated options and selected queries are bound to user, engine, connection, dialect, workspace, expiry, and execution state
- React cannot send raw SQL for preview or execution
- database URLs and credentials are never logged or returned to React
