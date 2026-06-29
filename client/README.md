# Client

Target location for the React frontend.

Current status:

- React + Vite scaffold is implemented.
- React Router and Axios are configured.
- `vanilla-reference/` contains the previous working HTML, CSS, and vanilla JavaScript frontend retained for UI and workflow reference.

Rules:

- The React client must call only the Node.js + Express server.
- The React client must never call `sql-service/` directly.
- Secrets, database URLs, API keys, and service-to-service credentials must never be placed in this folder.
- `VITE_API_BASE_URL` must point to the Express `/api` base URL only.

## Run

```bash
npm install
cp .env.example .env
npm run dev
```

Example local `.env` value:

```env
VITE_API_BASE_URL=http://127.0.0.1:5000/api
```
