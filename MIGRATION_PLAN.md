# Migration Plan

## Current Architecture

The repository currently contains a single application with:

- Vanilla HTML, CSS, and JavaScript frontend in `frontend/`
- Python FastAPI backend in `backend/`
- SQLAlchemy ORM models in `backend/models.py`
- SQLite relational database at `database/company.db`
- JWT authentication and bcrypt password hashing in the FastAPI backend
- Gemini-based SQL generation in `backend/sql_generator.py`
- sqlglot SQL validation in `backend/sql_validator.py`
- Role-based access control in `backend/authorization.py`
- Schema reading in `backend/schema_reader.py`
- Row-level enforcement and preview in `backend/impact_analyzer.py`
- Safe execution in `backend/query_executor.py`
- Query history, selected queries, and audit logs stored in SQLite
- pytest test suite in `tests/`

Current runtime shape:

```text
Browser
  -> Vanilla JS frontend
  -> FastAPI backend
  -> SQLite database
  -> Gemini API for generation when configured
```

Important current coupling:

- FastAPI owns authentication, user roles, query generation, SQL validation, preview, execution, history, and audit logs.
- SQLite stores both application/security data and target relational demo data.
- `backend/.env` defines `DATABASE_URL`, but `backend/database.py` currently hardcodes `database/company.db`.

## Target Architecture

The target architecture should split application concerns across three layers:

```text
React Frontend
  -> Node.js + Express API Gateway
      -> MongoDB for users, roles, policies, query history, selected queries, audit logs
      -> Python FastAPI SQL/NLP Service
          -> Target relational database: PostgreSQL, MySQL, or SQLite
          -> Gemini API
```

Target responsibilities:

### React Frontend

- Login and session UI
- Prompt composer
- Query option cards
- Selected-query workflow
- Preview results
- Execution confirmation
- Query history and audit views
- Security context display

### Node.js + Express Backend

- Public API entrypoint for the frontend
- JWT authentication
- Password hashing
- User registration and login
- Role and policy storage
- Request authorization before calling Python service
- Query history storage
- Selected query storage
- Audit logging
- Proxy/orchestration calls to Python FastAPI service

### MongoDB

Stores application/security metadata:

- Users
- Roles
- Policies
- Generated query options
- Selected queries
- Query history
- Audit logs
- User sessions or token metadata if needed

### Python FastAPI SQL/NLP Service

Keeps the strongest reusable security logic:

- Schema reading from target relational database
- AI/NLP SQL generation
- SQL validation using sqlglot
- Row-level SQL enforcement
- Query preview and impact analysis
- Safe execution against PostgreSQL, MySQL, or SQLite

### Target Relational Database

Stores business data queried by the SQL assistant:

- PostgreSQL, MySQL, or SQLite
- Example tables such as Employee and Students
- Future schemas can be inspected dynamically

## Reusable Files

These files can be reused directly or migrated with minimal changes:

- `backend/sql_generator.py`
  - Reuse in Python service for Gemini prompts, JSON normalization, and fallback generation.
- `backend/sql_validator.py`
  - Reuse in Python service for sqlglot validation.
- `backend/schema_reader.py`
  - Reuse in Python service, but adapt it for multiple target database URLs and dialects.
- `backend/impact_analyzer.py`
  - Reuse in Python service for preview and row-level SQL enforcement.
- `backend/query_executor.py`
  - Reuse in Python service, but make the database connection target configurable.
- `backend/authorization.py`
  - Reuse rules as a reference; final policy source should move to MongoDB/Express.
- `backend/schemas.py`
  - Reuse response shapes as API contracts for Express to Python communication.
- `tests/test_sql_validator.py`
  - Reuse for Python service tests.
- `tests/test_impact_analyzer.py`
  - Reuse for Python service tests after decoupling history storage.
- `tests/test_query_executor.py`
  - Reuse for Python service tests after target database abstraction.
- `tests/test_schema_reader.py`
  - Reuse for Python service tests.
- `tests/test_sql_generator.py`
  - Reuse for Gemini/fallback behavior.
- `frontend/index.html`, `frontend/style.css`, `frontend/script.js`
  - Reuse design ideas and UX flow while rebuilding as React components.
- `README.md`, `SECURITY.md`, `PROJECT_REPORT.md`
  - Reuse documentation content and update after each migration phase.

## Files to Deprecate

These files should eventually be replaced or split:

- `frontend/index.html`
  - Replace with React entrypoint such as `frontend/src/App.jsx`.
- `frontend/script.js`
  - Replace with React state, hooks, and API client modules.
- `frontend/style.css`
  - Migrate into React app styling, either global CSS or component-level CSS.
- `backend/main.py`
  - Split into two services:
    - Express routes for auth/history/audit/selection.
    - FastAPI routes for schema/generate/validate/preview/execute.
- `backend/models.py`
  - Split models:
    - MongoDB/Mongoose models for users, roles, policies, selected queries, history, audit logs.
    - SQLAlchemy or SQL driver logic only for target relational tables.
- `backend/database.py`
  - Replace with separate connection modules:
    - Express MongoDB connection.
    - Python target relational database connection.
- `backend/auth.py`
  - Reimplement in Node.js using bcrypt and jsonwebtoken.
- `backend/dependencies.py`
  - Replace auth dependencies with Express middleware.
- `backend/audit_logger.py`
  - Move audit persistence to Express/MongoDB.
- `backend/selected_query.py`
  - Move selected-query persistence to Express/MongoDB.

## Duplicate, Dead, Incomplete, or Conflicting Code

### Conflicting

- `backend/.env` and `backend/.env.example` define `DATABASE_URL`, but `backend/database.py` hardcodes the SQLite path with `DATABASE_PATH` and `DATABASE_URL`.
- `QueryHistory` is used for both generated options and execution history. In the target architecture, generated options and history should be separate MongoDB collections.
- FastAPI currently owns both application metadata and target relational data. The target architecture separates these into MongoDB and relational database access.

### Dead or Legacy-Like

- `backend/query_executor.py` includes `execute_read_only_query`, which appears to be a standalone helper not used by current endpoints.
- `backend/sql_validator.py` includes `is_select_only` and `_ReadOnlyUser`, marked as compatibility support for older starter tests.
- `backend/schema_reader.py` includes `read_schema`, while endpoints use `read_accessible_schema`.

### Incomplete for Target Architecture

- No React app exists yet.
- No Node.js or Express app exists yet.
- No MongoDB connection or schema exists yet.
- No service-to-service contract exists between Express and Python.
- No support exists yet for choosing PostgreSQL/MySQL/SQLite target database at runtime.
- No Docker Compose or multi-service local development setup exists yet.
- No integration tests exist for Express-to-FastAPI communication because Express does not exist yet.

### Not Present

- No Java files.
- No Spring Boot files.
- No Node package files.
- No React source files.
- No MongoDB models or migrations.

## Migration Phases

### Phase 0: Baseline Verification

Goal:

Confirm the current project is stable before migration begins.

Actions:

- Run existing Python tests.
- Run frontend JavaScript syntax check.
- Record current API behavior.
- Do not change architecture yet.

Commands:

```bash
cd secure-ai-sql-query-generator
python3 -m pytest
node --check frontend/script.js
python3 -m compileall backend tests
```

Risks:

- Current `.env` may contain local-only values.
- Gemini calls depend on external API key and network.

### Phase 1: Define Service Contracts

Goal:

Design the API boundary between Express and FastAPI before moving code.

Actions:

- Document request/response contracts for:
  - schema
  - generate
  - select query
  - preview
  - execute
  - validation result
- Decide what user context Express sends to Python:
  - user_id
  - role
  - department
  - employee_id
  - student_id
  - policy identifiers
- Decide how Python returns audit-worthy events to Express.

Commands:

```bash
python3 -m pytest
```

Risks:

- If contracts are vague, security rules may be enforced inconsistently.
- User context must be signed or trusted only over internal service calls.

### Phase 2: Add React Frontend Beside Existing Frontend

Goal:

Introduce React without breaking the current vanilla frontend.

Actions:

- Create a new React app in `frontend-react/` or replace `frontend/` only after parity is reached.
- Rebuild the current UI as React components:
  - LoginPanel
  - SecurityStatus
  - PromptComposer
  - QueryOptions
  - PreviewPanel
  - ExecutionPanel
  - HistoryPanel
  - ConfirmationModal
- Keep API calls compatible with the current FastAPI backend at first.

Commands:

```bash
npm create vite@latest frontend-react -- --template react
cd frontend-react
npm install
npm run dev
npm run build
```

Risks:

- Token handling can regress if local/session storage behavior changes.
- Frontend must not become the authority for permissions.

### Phase 3: Add Node.js + Express Backend

Goal:

Introduce Express as the frontend-facing API gateway.

Actions:

- Create `server/` or `node-backend/`.
- Add Express, cors, dotenv, bcrypt, jsonwebtoken, mongoose, helmet, and validation middleware.
- Implement:
  - `/auth/register`
  - `/auth/login`
  - `/auth/me`
  - `/history`
  - `/admin/audit-logs`
  - `/queries/select`
  - `/queries/selected`
- Initially proxy schema/generate/preview/execute to the existing FastAPI backend.

Commands:

```bash
mkdir node-backend
cd node-backend
npm init -y
npm install express cors dotenv bcrypt jsonwebtoken mongoose helmet zod
npm install -D nodemon jest supertest
npm test
```

Risks:

- JWT secrets must be consistent or intentionally separate between services.
- Express must not trust frontend role claims.
- Express must validate all request bodies.

### Phase 4: Move Auth, Roles, Policies, History, Selection, and Audit to MongoDB

Goal:

Make MongoDB the source of truth for application/security data.

Actions:

- Create Mongoose models:
  - User
  - RolePolicy
  - GeneratedQuery
  - SelectedQuery
  - QueryHistory
  - AuditLog
- Port bcrypt password hashing and JWT creation to Express.
- Store generated options in MongoDB instead of SQLite QueryHistory.
- Store selected queries in MongoDB with TTL index.
- Store audit logs in MongoDB.
- Keep Python focused on SQL/NLP and target relational database operations.

Commands:

```bash
cd node-backend
npm test
npm run dev
```

If using local MongoDB:

```bash
mongod
```

Risks:

- Data model mismatch between SQLAlchemy integer IDs and MongoDB ObjectIds.
- Audit logs must not store passwords, tokens, or secrets.
- Selected query expiry should be enforced server-side with TTL indexes and runtime checks.

### Phase 5: Refactor Python into Dedicated SQL/NLP Service

Goal:

Keep Python as a specialized service for schema reading, generation, validation, preview, and safe execution.

Actions:

- Rename or restructure `backend/` as `python-sql-service/`.
- Remove user registration/login endpoints from Python.
- Accept trusted user context from Express for each request.
- Keep:
  - schema reader
  - Gemini SQL generator
  - SQL validator
  - row-level enforcement
  - preview
  - execution
- Add support for target database configuration:
  - SQLite
  - PostgreSQL
  - MySQL
- Add database dialect selection for sqlglot and SQLAlchemy.

Commands:

```bash
cd python-sql-service
python3 -m pytest
uvicorn main:app --reload --port 8001
```

Risks:

- Python service must not accept arbitrary user context from public clients.
- Only Express should call internal Python routes.
- SQL dialect differences may break validation or execution.

### Phase 6: Connect Express to Python Service

Goal:

Make Express orchestrate the complete workflow.

Actions:

- Frontend calls Express only.
- Express authenticates user and loads policy from MongoDB.
- Express calls Python with sanitized user context.
- Python returns query options, validation, preview, or execution result.
- Express stores generated options, selected queries, history, and audit logs in MongoDB.

Commands:

```bash
cd node-backend
npm test

cd ../python-sql-service
python3 -m pytest
```

Risks:

- Preview and execution must both repeat validation and authorization.
- Express and Python must agree on selected query IDs and generated SQL source.
- Network failures between services need safe error handling.

### Phase 7: Add Target Relational Database Adapters

Goal:

Support PostgreSQL, MySQL, and SQLite as target databases.

Actions:

- Add environment variables for target DB:
  - `TARGET_DB_TYPE`
  - `TARGET_DATABASE_URL`
  - `SQL_DIALECT`
- Add SQLAlchemy drivers:
  - PostgreSQL: `psycopg`
  - MySQL: `pymysql`
  - SQLite: built in
- Add adapter tests for schema reading and validation.

Commands:

```bash
cd python-sql-service
pip install psycopg pymysql
python3 -m pytest
```

Risks:

- SQL syntax varies by database.
- Preview count wrappers may need dialect-specific handling.
- Target database credentials must not be exposed to React or MongoDB logs.

### Phase 8: Full Integration and Security Testing

Goal:

Verify the final multi-service architecture.

Actions:

- Add integration tests for:
  - React to Express
  - Express to MongoDB
  - Express to Python
  - Python to target relational database
- Add security tests for:
  - invalid JWT
  - role bypass attempt
  - direct Python service access attempt
  - SQL injection attempt
  - UPDATE/DELETE without preview
  - DCL/DDL/TCL handling
- Add audit log tests.

Commands:

```bash
cd frontend-react
npm run build

cd ../node-backend
npm test

cd ../python-sql-service
python3 -m pytest
```

Risks:

- Multi-service tests are slower and require stable local services.
- CORS and service URLs can drift between dev and production.

## Overall Risks

- Splitting one backend into two services can introduce authorization gaps if responsibilities are unclear.
- User context sent from Express to Python must be protected and never accepted from the browser directly.
- Query option selection must remain server-side; frontend SQL must never be trusted.
- Preview and execution must both repeat validation and row-level enforcement.
- MongoDB audit logs must redact secrets.
- Relational target database credentials must be isolated from frontend and MongoDB.
- SQL dialect differences may require separate validation and execution tests.
- Keeping both old and new frontends during migration may create duplicated UI logic.

## Recommended Safest Path

The safest migration path is incremental:

1. Keep the existing FastAPI project working.
2. Add React frontend while still calling FastAPI.
3. Add Express backend while proxying to FastAPI.
4. Move authentication, roles, history, selected queries, and audit logs from FastAPI/SQLite to Express/MongoDB.
5. Refactor FastAPI into an internal Python SQL/NLP service.
6. Add target database adapters for PostgreSQL, MySQL, and SQLite.
7. Run full security and integration tests before removing old files.

This avoids a risky rewrite and preserves the currently tested SQL validation and row-level security logic during the transition.
