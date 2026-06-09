# Local Setup

## Prerequisites

- Git
- Python 3.11 or newer
- Node.js 22 or newer and npm
- Docker with Compose, if running PostgreSQL and Redis locally

The repository is an early scaffold. Python, Node dependencies, and package
lockfiles are not bundled in the checkout.

## Environment Safety

`backend/.env.example` contains variable names and development placeholders.
Create `backend/.env` for local values. Do not put real API keys, telephony
tokens, database credentials, or signing secrets in documentation, commits,
shell history, screenshots, or issue reports.

```powershell
Copy-Item backend\.env.example backend\.env
```

```bash
cp backend/.env.example backend/.env
```

Replace insecure placeholders only in the ignored `.env` file. External AI
and telephony credentials are not required for the current health endpoint.

## Backend

PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```

Bash:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```

Verify:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

```bash
curl http://localhost:8000/health
```

Expected status is `ok`. Interactive API documentation is available at
`http://localhost:8000/docs`.

Apply database migrations from the backend directory:

```powershell
python -m alembic upgrade head
```

The command uses `DATABASE_URL` from `backend/.env`. The default local value
creates `backend/local.db`; set a PostgreSQL URL in the ignored `.env` file
when testing against PostgreSQL.

## Frontend

In a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

The same commands work in Bash. Open `http://localhost:3000`.

The frontend defaults to `http://localhost:8000/api/v1`. To override it, set
`NEXT_PUBLIC_API_BASE_URL` in an ignored `frontend/.env.local` file.

## PostgreSQL and Redis

Start only the supporting services:

```powershell
docker compose up -d postgres redis
```

Stop them:

```powershell
docker compose down
```

PostgreSQL and Redis are declared but not yet connected to implemented
persistence code. The full `docker compose up --build` path is scaffolding and
should not be treated as a validated production-like environment.

## Tests and Checks

Backend:

```powershell
cd backend
python -m pytest -q
python -m ruff check .
python -m mypy app
```

Frontend:

```powershell
cd frontend
npm run build
```

The current repository has one backend health test and no frontend test script.
See `docs/repo_audit.md` for known baseline gaps.

## Common Problems

- **`python` not found:** Install Python 3.11+ and restart the terminal.
- **PowerShell blocks activation:** Use a process-scoped execution policy or
  run the commands from a shell permitted by local policy.
- **`next` not found:** Run `npm install` inside `frontend/`.
- **Port already in use:** Stop the existing process or select another local
  port.
- **Database connection from a container fails:** Container connections must
  use Compose service names such as `postgres` and `redis`, not `localhost`.
