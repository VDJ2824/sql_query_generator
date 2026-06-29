# API Contract

This document describes the boundary between React, Express, MongoDB, and the Python SQL service.

## Client To Express

React must call only the Express API. It must not call `sql-service/` directly.

Implemented Express routes:

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/verify-login-otp`
- `GET /api/auth/me`
- `GET /api/database-connections`
- `POST /api/database-connections`
- `POST /api/queries/generate`
- `POST /api/queries/select`
- `POST /api/queries/preview`
- `POST /api/queries/execute`
- `GET /api/history`
- `GET /api/admin/audit-logs`

React may send:

- login/register form values
- login OTP value after the backend has created an OTP challenge
- natural language prompt
- selected `databaseConnectionId`
- selected `optionId`
- execution confirmation flag
- required confirmation token or typed confirmation for destructive approved operations

Public signup accepts only:

- `username`
- `email`
- `password`
- `confirmPassword`

React must not send trusted:

- role
- policies
- allowed schemas
- allowed tables
- allowed columns
- executable SQL for preview or execution
- workspace identifiers, schema names, or database names
- MongoDB IDs for user impersonation

## Express To MongoDB

Express stores and loads:

- users
- database connection metadata
- access policies
- generated query options
- selected queries
- query history
- audit logs

Target database passwords and connection URLs are not stored in React responses. Database connection metadata stores only the target credential environment variable name. Private workspace identifiers stay in MongoDB and internal Express-to-FastAPI payloads only.

## Express To SQL Service

Only Express may call the SQL service.

Internal routes:

- `POST /internal/schema`
- `POST /internal/generate`
- `POST /internal/preview`
- `POST /internal/execute`

Every internal route requires:

```http
x-internal-api-key: <SQL_SERVICE_API_KEY>
```

FastAPI must not receive this context from the browser. Express builds it after JWT verification and MongoDB lookups.

Internal request shape:

```json
{
  "verifiedUser": {
    "userId": "mongo-user-id",
    "role": "USER"
  },
  "databaseConnection": {
    "connectionId": "mongo-connection-id",
    "databaseType": "postgresql",
    "dialect": "postgres",
    "credentialEnvironmentVariableName": "POSTGRES_DEMO_URL"
  },
  "accessPolicies": [
    {
      "role": "USER",
      "databaseConnectionId": "mongo-connection-id",
      "allowedOperations": ["DQL", "DML"],
      "allowedSchemas": [],
      "allowedTables": ["employee", "students", "department"],
      "blockedTables": ["users", "audit_logs", "query_history", "selected_queries"],
      "allowedColumns": [],
      "requiresPreviewFor": ["INSERT", "UPDATE", "DELETE"],
      "requiresConfirmationFor": ["INSERT", "UPDATE", "DELETE"],
      "active": true
    }
  ],
  "prompt": "Show employees whose salary is greater than 50000",
  "generatedSql": "SELECT name, email, department, salary FROM Employee WHERE salary > 50000",
  "selectedOptionId": 1,
  "confirmed": false
}
```

Generate response:

```json
{
  "queryOptions": [
    {
      "optionId": 1,
      "title": "Sales by region",
      "generatedSql": "SELECT region, amount FROM sales",
      "finalEnforcedSql": "SELECT region, amount FROM sales",
      "securityFilterExplanation": "No identity-based row-level restriction is configured for this general SQL policy.",
      "databaseType": "SQLITE",
      "sqlDialect": "sqlite",
      "queryType": "SELECT",
      "tablesUsed": ["sales"],
      "columnsUsed": ["region", "amount"],
      "explanation": "Shows allowed sales columns.",
      "riskLevel": "low",
      "executionAllowed": true,
      "requiresConfirmation": false,
      "warnings": []
    }
  ]
}

```

## Security Contract

- Express must verify JWT before protected requests.
- Express must load trusted user and policy context from MongoDB.
- Express must store generated options server-side.
- Express must select by `optionId` only.
- Express must retrieve selected SQL server-side before preview and execution.
- SQL service must validate AI SQL before returning options.
- SQL service must validate again before preview.
- SQL service must validate again before execution.
- TCL commands must be view-only.
- DCL and dangerous DDL commands must be blocked.
- INSERT, UPDATE, and DELETE must require preview and confirmation when enabled by policy.
