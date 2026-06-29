# Server

Target location for the Node.js + Express + MongoDB backend.

Current status:

- Express app scaffold is implemented.
- MongoDB/Mongoose models are implemented for users, connection metadata, access policies, selected queries, history, and audit logs.
- Express integrates with the internal Python `sql-service/` for schema, SQL generation, preview, and execution.
- SQL/NLP and relational database connections are intentionally not implemented directly in Express.

Planned responsibilities:

- User registration and login
- JWT issuing and verification
- Role and policy loading
- MongoDB storage for users, policies, selected queries, query history, and audit logs
- Frontend-facing API routes
- Internal calls to `sql-service/`

Implemented query routes:

- `POST /api/queries/generate`
- `POST /api/queries/select`
- `POST /api/queries/preview`
- `POST /api/queries/execute`

Required environment variables:

```env
MONGODB_URI=
JWT_SECRET=
JWT_EXPIRES_IN=1h
SQL_SERVICE_URL=
SQL_SERVICE_API_KEY=
CLIENT_URL=
```

Use `SQL_SERVICE_URL=http://127.0.0.1:8001` for local development and `SQL_SERVICE_URL=http://sql-service:8001` inside Docker Compose.

Rules:

- Only this server may call `sql-service/`.
- The client must never call `sql-service/` directly.
- Never trust role, policy, or SQL data sent from the client.
- React sends only prompt, option selection, and confirmation data.
- Express loads the verified user, active database connection, and access policies from MongoDB.
- Express stores generated query options server-side.
- Preview and execution always use the selected server-side query, never arbitrary SQL from React.
- Selected queries expire after 15 minutes, and each user can have only one active selected query.
- Selected query documents store generated SQL and final enforced SQL separately.
- `INSERT`, `UPDATE`, and `DELETE` execution is blocked until the selected query has been previewed.
- Every preview and execution attempt is audited, including blocked attempts.
- Do not expose `SQL_SERVICE_URL`, `SQL_SERVICE_API_KEY`, target database URLs, or credential environment variable names to React.

## Run

```bash
npm install
cp .env.example .env
npm run seed
npm run dev
```

For local development, a typical `.env` points `MONGODB_URI` at local MongoDB and `SQL_SERVICE_URL` at the local Python service. Keep real secrets in `.env`, not in `.env.example`.

## Test

```bash
npm test
```
