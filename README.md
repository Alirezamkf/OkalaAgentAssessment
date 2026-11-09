# Okala Agent Assessment

An initial project skeleton for an agent-based assessment platform developed for Okala through CafeTadris. The current scope is architecture and infrastructure validation only. Assessment workflows, authentication, recording, and AI behavior are intentionally not implemented.

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

Copy `.env.example` to `.env` and replace the local PostgreSQL password before starting the stack:

```powershell
Copy-Item .env.example .env
```

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
