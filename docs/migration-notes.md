# Migration Notes

## What Changed in This Preparation Step

- Created target folders:
  - `client/`
  - `server/`
  - `sql-service/`
  - `docs/`
  - `legacy/`
- Moved the previous FastAPI monolith into:
  - `legacy/fastapi-monolith/backend/`
  - `legacy/fastapi-monolith/tests/`
- Moved the previous vanilla frontend into:
  - `client/vanilla-reference/`
- Copied reusable SQL/NLP Python modules into:
  - `sql-service/reference-modules/`

## What Has Not Been Implemented Yet

- React frontend
- Express backend
- MongoDB schemas
- Service-to-service authentication
- Dedicated Python SQL service routes
- PostgreSQL/MySQL target database adapters
- Dockerfiles for client, server, or SQL service

## Why Legacy Is Kept

The previous implementation contains working logic and tests. It is retained so the migration can safely reuse:

- SQL validation rules
- row-level enforcement rules
- query preview logic
- safe execution workflow
- frontend UX ideas
- existing test cases

## Important Warning

Do not remove `legacy/` until the new architecture has equivalent tests and behavior.
