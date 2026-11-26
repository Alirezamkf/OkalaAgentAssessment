# Okala Agent Assessment

An initial project skeleton for an agent-based assessment platform developed for Okala through CafeTadris. The current scope is architecture and infrastructure validation only. End-user authentication, assessment workflows, recording, and AI behavior are intentionally not implemented. Backend-to-Agent service authentication is configured separately through a shared local/deployment credential.

## Technology Stack

- Frontend: Next.js App Router, React, TypeScript, Bootstrap
- Backend: Python, FastAPI, REST API
- Agent service: independent Python/FastAPI placeholder
- Database: PostgreSQL, accessed by the backend only
- Infrastructure: Docker and Docker Compose

## Architecture

The frontend calls the backend REST API. The backend owns PostgreSQL access and communicates with independent agent services through APIs. Agents do not connect directly to PostgreSQL. Video storage remains undecided and is represented by `storage/videos`.

## Directory Structure

```text
frontend/                 Next.js application
backend/                  FastAPI application and backend tests
agents/agent_service/     Independent generic agent placeholder
storage/videos/           Reserved video storage location
infrastructure/           Docker and CI/CD placeholders
docker-compose*.yml       Development and production service orchestration
```

## Prerequisites

- Docker Desktop with Compose
- Node.js 22+ and npm (for local frontend checks)
- Python 3.12+ (for local backend checks)

## Environment Configuration

Copy `.env.example` to `.env`, replace `CHANGE_ME` with a local PostgreSQL password,
and set `AGENT_SERVICE_SHARED_SECRET` to a locally generated random value:

```powershell
Copy-Item .env.example .env
```

Generate a value with Python, then place the same value in the local `.env` file:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Docker Compose passes this credential only to Backend and Agent Service. Leave
it unset to keep the Backend available without Agent Service calls; the Agent
health endpoint remains public, while protected AI requests fail safely until
the shared credential is configured. The Frontend must never receive this
credential.

Keep `.env` local and never commit it. Docker Compose uses `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` for both PostgreSQL and the Backend `DATABASE_URL`. Each developer should use a separate local `.env` and may therefore have an independent local database volume and credentials.

For database URL compatibility, use URL-safe characters in the local PostgreSQL password because the password is placed in the Compose-generated SQLAlchemy URL. Characters such as `/`, `@`, `#`, `?`, and `%` can require URL encoding.

Start the stack and apply the shared Alembic migrations:

```powershell
docker compose up --build
docker compose exec backend alembic upgrade head
```

A developer who already has a running volume can use the same migrations to update its local schema; do not share or delete another developer's volume.

Do not commit `.env` or real secrets.

## Development

Start all services with development-oriented configuration:

```powershell
docker compose up --build
```

Stop the stack:

```powershell
docker compose down
```

Run the frontend locally:

```powershell
Set-Location frontend
npm install
npm run dev
```

## Continuous Integration

The GitHub Actions CI workflow runs frontend linting and production builds, backend and agent-service tests, and Docker Compose validation and image builds. It runs for pushes to `main`, pull requests targeting `main`, and manual dispatches. Open the repository's **Actions** tab on GitHub to view workflow runs and check results.

## Production

Set production values in `.env`, then build and start without source mounts:

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

Stop production services:

```powershell
docker compose -f docker-compose.prod.yml down
```

## Service URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Agent service: http://localhost:8001
- PostgreSQL: internal Docker network only

## Health Checks

```text
GET http://localhost:8000/api/v1/health
GET http://localhost:8001/health
```

Expected responses are `{"status":"healthy","service":"backend"}` and `{"status":"healthy","service":"agent"}` respectively. The frontend homepage displays all three service states and remains usable when either API is unavailable.
