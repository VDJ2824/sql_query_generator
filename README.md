# Secure AI SQL Query Generator

A beginner-friendly college project that converts natural language prompts into SQL query options, then validates, authorizes, previews, and executes them safely.

The central rule is simple: AI-generated SQL is never trusted directly. Every query is validated and authorized again before preview, and again before execution.

## Tech Stack

- Backend: Python 3, FastAPI, SQLAlchemy, SQLite, JWT, bcrypt, sqlglot, Gemini API
- Frontend: HTML, CSS, Vanilla JavaScript
- Database: SQLite development database at `database/company.db`
- Tests: pytest and FastAPI TestClient

## Main Features

- JWT authentication with bcrypt password hashing
- Role-based access control for admin, manager, employee, faculty, and student users
- Dynamic schema visibility based on the logged-in user's role
- Natural-language-to-SQL generation with Gemini plus rule-based fallback generation
- Server-side query option storage and temporary selected-query records
- SQL parsing and validation with sqlglot
- Row-level security enforcement for employee, student, manager, and faculty access
- Safe preview workflow for SELECT, UPDATE, and DELETE
- Confirmation requirement for data-changing queries
- TCL commands are view-only
- DCL and dangerous DDL commands are blocked
- Query history and audit logging
- Frontend that escapes displayed text and handles 401/403 responses safely

## Setup

1. Create a virtual environment from the project root.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install backend packages.

```bash
cd backend
pip install -r requirements.txt
cd ..
```

3. Copy the example environment file.

```bash
cp backend/.env.example backend/.env
```

4. Edit `backend/.env`.

```text
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
DATABASE_URL=sqlite:///../database/company.db
```

5. Run the backend from the project root.

```bash
uvicorn backend.main:app --reload
```

6. Open the frontend.

```bash
cd frontend
python3 -m http.server 5500
```

Then open `http://127.0.0.1:5500` in a browser.

## Seeded Test Users

The database initializes with sample employees, students, and users when it is empty.

```text
admin / admin123
it_manager / manager123
hr_manager / manager123
employee_6 / employee123
student_1 / student123
faculty_1 / faculty123
```

## Authentication Examples

Register a test user. Registration is open only for project testing; a production app should restrict it to admins.

```bash
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analyst_test",
    "password": "test123",
    "role": "employee",
    "department": "IT",
    "employee_id": 6
  }'
```

Log in.

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Use the returned token.

```bash
TOKEN="paste_access_token_here"
curl http://127.0.0.1:8000/me \
  -H "Authorization: Bearer $TOKEN"
```

## Query Workflow

1. Log in and request `/schema` to see only the allowed tables and columns.
2. Submit a natural language prompt to `/generate`.
3. Select one generated option through `/select-query`.
4. Preview the selected query through `/preview-selected-query`.
5. Execute through `/execute-selected-query`.
6. UPDATE, INSERT, and DELETE require explicit confirmation when allowed.
7. Every important event is logged through audit records.

## Security Rules

- AI output is treated as untrusted input.
- Password hashes are never returned in API responses.
- JWT tokens are required for protected endpoints.
- Restricted tables such as Users, QueryHistory, and AuditLogs are not exposed through schema or normal SQL access.
- `password_hash` is always restricted.
- Multiple statements and SQL comments are rejected.
- JOIN and UNION are rejected in this starter project because they can complicate row-level enforcement.
- UPDATE and DELETE must contain WHERE clauses.
- UPDATE and DELETE require preview and confirmation.
- TCL commands are never executed.
- DCL and dangerous DDL commands are blocked.
- Audit logs redact common password, token, secret, and API key patterns.

More details are in `SECURITY.md`.

## Running Tests

Run the complete test suite from the project root.

```bash
python3 -m pytest
```

Run syntax checks.

```bash
python3 -m compileall backend tests
node --check frontend/script.js
```

## Useful Endpoints

- `GET /health`
- `POST /register`
- `POST /login`
- `GET /me`
- `GET /schema`
- `POST /generate`
- `POST /select-query`
- `GET /selected-query`
- `POST /preview-selected-query`
- `POST /execute-selected-query`
- `GET /history`
- `GET /admin/audit-logs`

## Important Development Notes

- SQLite is used for development and demonstration.
- The frontend stores the JWT in `sessionStorage` for this demo. A production deployment should use stricter browser storage and HTTPS-only protections.
- The frontend may hide buttons for convenience, but the backend always enforces authorization.
- Replace the demo `SECRET_KEY` before sharing or deploying the backend.
