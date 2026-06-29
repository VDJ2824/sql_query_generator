# Cloud Refactor Plan

## Current Architecture

- `client/` is a React/Vite frontend.
- `server/` is an Express API that owns authentication, MongoDB metadata, generated options, selected queries, history, and audit logs.
- `sql-service/` is a FastAPI service that reads target schemas, generates SQL, validates SQL, previews queries, and executes safe SQL.
- Docker Compose currently supports local containers for MongoDB, PostgreSQL, MySQL, and service networking.
- The active seed currently creates local demo database connection metadata for SQLite, PostgreSQL, and MySQL.
- The SQL service currently has per-user workspace helpers for SQLite files, PostgreSQL schemas, and MySQL databases.

## Target Architecture

React frontend -> Express backend -> FastAPI SQL service -> managed target databases:

- MongoDB Atlas stores users, password hashes, database connection metadata, policies, generated options, selected queries, history, and audit logs.
- Neon PostgreSQL is accessed through `POSTGRES_DEMO_URL` using SQLAlchemy and psycopg.
- TiDB Cloud is accessed through `MYSQL_DEMO_URL` using SQLAlchemy and PyMySQL.
- React never receives target database URLs, provider details, internal API keys, or SQL service credentials.

## Docker Dependency Points

- `docker-compose.yml` uses `mongo`, `postgres`, `mysql`, and `sql-service` service names.
- `docker-compose.production.yml` provisions container PostgreSQL and MySQL services.
- README and deployment docs include Docker startup, Docker hostnames, and Docker volume instructions.
- Seed data names currently use `Local SQLite Demo`, `Local PostgreSQL Demo`, and `Local MySQL Demo`.
- `sql-service/app/db.py` creates local/private workspaces and SQLite files.

## Hardcoded Or Docker-Specific Connection Assumptions

- `mongodb://mongo:27017/sql-query-generator`
- `http://sql-service:8001`
- `postgres:5432`
- `mysql:3306`
- `/app/database/company.db`
- `SQLITE_DEMO_PATH`
- Docker init folders under `database/postgres-init/` and `database/mysql-init/`
- Production Docker init folders under `deploy/postgres/init/` and `deploy/mysql/init/`

## Phase 1 Migration Strategy

1. Keep Docker files for reference, but mark Docker Compose as deprecated for normal development/deployment.
2. Use non-Docker local development commands for React, Express, and FastAPI.
3. Use `MONGODB_URI` for MongoDB Atlas.
4. Seed two active target connections only:
   - `Neon PostgreSQL`
   - `MySQL-compatible (TiDB Cloud)`
5. Remove SQLite from active seeded database choices.
6. Disable per-user database/schema/file creation in the active SQL service for Phase 1.
7. Keep generated/selected query metadata bound to user, connection id, database type, dialect, and expiry.
8. Add idempotent cloud database initialization scripts for Neon and TiDB sample tables.
9. Keep SQL validation and execution rules:
   - `SELECT`, `INSERT` allowed by policy.
   - `UPDATE`, `DELETE` require preview and confirmation.
   - Allow-listed table/index `DDL` allowed by policy with preview and confirmation; destructive/unrestricted database administration blocked.
   - `DCL`, `TCL`, database administration, and cross-database access blocked.

## Phase 1 Implementation Status

- Docker compose files are retained but marked deprecated.
- `.env.example`, `.env.cloud.example`, `server/.env.example`, `sql-service/.env.example`, and `client/.env.example` now use managed-cloud placeholders.
- Seeded active database connections are now:
  - `Neon PostgreSQL Demo`
  - `TiDB Cloud MySQL-Compatible Demo`
- Old SQLite metadata is deactivated by the seed script.
- Seeded policies allow DQL, DML, and allow-listed DDL. DDL requires preview and confirmation.
- `sql-service/app/db.py` no longer creates SQLite workspace files, PostgreSQL schemas, or MySQL databases during request handling.
- `sql-service/scripts/init_cloud_databases.py` initializes demo tables and sample data in Neon/PostgreSQL and TiDB/MySQL-compatible databases.
- React database selection no longer advertises SQLite as a normal active target.
- README and SECURITY now describe the cloud-first workflow.

## Risks

- Cloud database URLs must be URL-encoded and must include provider-required SSL/TLS options.
- Existing MongoDB database connection records may still contain local Docker/SQLite records until seed is rerun.
- Neon/TiDB schemas must be initialized before useful schema-aware generation can return query options.
- Phase 1 uses shared target databases, so per-user physical isolation is not implemented yet.

## Commands After Phase 1

```bash
# Server metadata seed
cd server
npm install
npm run seed

# Initialize Neon PostgreSQL
cd ../sql-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_cloud_databases.py --target postgres

# Initialize TiDB Cloud
python scripts/init_cloud_databases.py --target mysql

# Run services without Docker
cd ../sql-service
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

cd ../server
npm run dev

cd ../client
npm install
npm run dev
```
