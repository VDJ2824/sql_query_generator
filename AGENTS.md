# Project Coding Rules

## Target Architecture

The repository is migrating toward this architecture:

- `client/`: React frontend.
- `server/`: Node.js + Express backend with MongoDB.
- `sql-service/`: Python FastAPI NLP and SQL service.
- `legacy/`: previous implementations retained for reference.
- `docs/`: architecture, API contract, and migration notes.

## Strict Architecture Rules

- React must never call `sql-service/` directly.
- Only the Express server may call `sql-service/`.
- MongoDB stores users, policies, selected queries, query history, and audit logs.
- Python `sql-service/` handles SQL intelligence and target RDBMS access.
- Never expose secrets to `client/`.
- Never store API keys, database URLs, JWT secrets, or service credentials in frontend code.
- AI-generated SQL must be validated before preview and again before execution.
- TCL commands are view-only.
- DCL and dangerous DDL commands are blocked.
- Row-level restrictions must be enforced by `sql-service/`.

## Migration Safety Rules

- Do not delete `legacy/` until equivalent functionality is implemented and tested in the new architecture.
- Do not move sample data, reports, environment examples, or reusable frontend assets without preserving them.
- Keep migration phases small and testable.
- Prefer copying useful legacy logic into the new service first, then deleting only after replacement tests pass.
- Keep service boundaries explicit in documentation and code.

## General Coding Rules

- Keep code modular and beginner-friendly.
- Prefer clear names over clever shortcuts.
- Keep secrets in environment variables, never in code.
- Keep SQL generation, validation, authorization, and execution separated.
- Treat all generated SQL as untrusted until it is validated.
- Add comments only where they help explain non-obvious logic.
- When adding new code, keep imports tidy and avoid unnecessary dependencies.
- Update tests whenever behavior changes.
