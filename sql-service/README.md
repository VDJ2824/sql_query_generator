# SQL Service

Internal Python FastAPI microservice for SQL intelligence and safe target-database access.

This service is called only by the Express backend. It does not provide login pages and does not connect to MongoDB for normal user authentication. Express verifies the user, loads MongoDB policies, and sends that verified context to this service.

## Responsibilities

- Read the selected target database schema dynamically with SQLAlchemy.
- Generate SQL options with Gemini when `GEMINI_API_KEY` is configured.
- Fall back to safe rule-based SQL options when Gemini is unavailable.
- Validate AI-generated SQL with `sqlglot`.
- Enforce row-level restrictions before preview and again before execution.
- Preview `SELECT`, `UPDATE`, and `DELETE` safely without modifying data.
- Execute only validated and authorized SQL against PostgreSQL, MySQL, or SQLite.

## Internal Endpoints

- `GET /health`
- `POST /internal/schema`
- `POST /internal/generate`
- `POST /internal/preview`
- `POST /internal/execute`

Every `/internal/*` endpoint requires:

```http
x-internal-api-key: your-internal-key
```

## Environment

Copy `.env.example` to `.env` and update the values:

```env
SQL_SERVICE_API_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
POSTGRES_DEMO_URL=
MYSQL_DEMO_URL=
SQLITE_DEMO_PATH=
```

The Express server sends `databaseConnection.credentialEnvironmentVariableName`. This service reads the real target database URL or SQLite path from that environment variable, so connection strings are never sent to the browser.

`POST /internal/generate` returns structured query alternatives:

```json
{
  "queryOptions": [
    {
      "optionId": 1,
      "title": "Detailed employee records",
      "generatedSql": "SELECT employee_id, name FROM employees",
      "finalEnforcedSql": "SELECT employee_id, name FROM employees WHERE employee_id = :rls_employee_id",
      "databaseType": "SQLITE",
      "sqlDialect": "sqlite",
      "queryType": "SELECT",
      "tablesUsed": ["employees"],
      "columnsUsed": ["employee_id", "name"],
      "explanation": "Validated SQL option generated for the request.",
      "riskLevel": "low",
      "executionAllowed": true,
      "requiresConfirmation": false,
      "warnings": []
    }
  ]
}
```

The generation layer is implemented by `SqlGenerationService`. It reads schema dynamically, filters the schema using Express-provided policies, asks Gemini for alternatives when configured, validates each generated query, removes unsafe or duplicate options, and falls back to rule-based options when the AI API is unavailable.

Supported target database URL examples:

```env
SQLITE_DEMO_PATH=../database/company.db
POSTGRES_DEMO_URL=postgresql+psycopg://user:password@localhost:5432/company
MYSQL_DEMO_URL=mysql+pymysql://user:password@localhost:3306/company
```

## Run Locally

```bash
cd sql-service
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Test

```bash
cd sql-service
python3 -m compileall app tests
python3 -m pytest -q
```

## Security Rules

- Do not trust the frontend.
- Do not trust AI-generated SQL.
- Do not trust raw user IDs, employee IDs, student IDs, or roles from the browser.
- Accept verified user context only from Express through the internal API.
- Use parameterized SQLAlchemy execution for row-level user-context values.
- Validate and authorize before preview.
- Validate and authorize again before execution.
- Validate generated SQL before returning query options.
- Return generated SQL and security-enforced SQL separately.
- TCL commands are view-only and cannot be executed.
- DCL and dangerous DDL commands are blocked.
- Row-level restrictions are enforced by this service.

## SQL Validation Policy

`sqlglot` is used to classify and validate SQL before preview and again before execution.

- `SELECT` is allowed only after syntax, schema, policy, and row-level checks.
- `INSERT`, `UPDATE`, and `DELETE` require access-policy permission, preview, and explicit confirmation.
- `UPDATE` and `DELETE` must include a `WHERE` clause.
- `INSERT` preview validates the statement and returns intended impact without modifying data.
- `UPDATE` and `DELETE` preview counts and displays affected rows without modifying data.
- TCL commands such as `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `RELEASE SAVEPOINT`, and `SET TRANSACTION` are view-only and never sent to the target database.
- DCL commands such as `GRANT` and `REVOKE` are blocked.
- Dangerous DDL commands such as `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `ATTACH`, and `PRAGMA` are blocked.
- Multiple statements, SQL comments, restricted tables, restricted columns, unknown commands, unsupported dialect syntax, unsafe joins, unions, CTEs, nested selects, and stored-procedure style commands are rejected.

## Row-Level Security Policy

`RowLevelSecurityService` applies row-level authorization filters using policies sent by Express. It returns `generatedSql`, `finalEnforcedSql`, and `securityFilterExplanation`.

Supported `rowFilterType` values:

- `SELF_EMPLOYEE_RECORD`: adds `employee_id = :employee_id`
- `SELF_STUDENT_RECORD`: adds `student_id = :student_id`
- `SAME_DEPARTMENT`: adds `department = :department`
- `ASSIGNED_STUDENTS`: adds `faculty_id = :faculty_id`
- `NO_RESTRICTION`: does not add a row filter

If the original SQL already has a `WHERE` clause, the enforced filter is combined with `AND`. User-provided conditions never replace the enforced filter, so a request like `WHERE employee_id = 2` still becomes `WHERE employee_id = 2 AND employee_id = :employee_id`.

For safety, row-level enforcement rejects joins, unions, CTEs, nested queries, and complex statements instead of guessing how to secure them.

## Reference Modules

`reference-modules/` contains useful Python logic copied from the previous FastAPI monolith for migration reference. These files are retained only for comparison and should not be imported by the running service.
