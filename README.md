# Gym__Data

Docker-first foundation for a fitness analytics platform built around real `workouts/*.json` and `measurements/*.json` source datasets.

## What is included
- PostgreSQL RAW layer for source-oriented workout facts and body measurement sessions
- ClickHouse MART layer for workout and measurement analytics
- FastAPI backend with health, workout detail, exercise progress, measurement progress, profile workspace, and analytics endpoints
- Embedded control panel UI served by the backend at `/ui/`
- Measurement write API for creating and updating body measurement sessions
- Ingestion job that validates, loads, and reconciles the existing workout and measurement JSON files
- Runbook and roadmap for the next platform stages

## Quick start
1. Optionally stop a previous `Gym__Data` run with `docker compose down`.
2. Copy `.env.example` to `.env` if you want to override defaults.
3. Run `docker compose up -d --build`.
4. Run `docker compose --profile jobs run --rm --build ingestion`.
5. Optionally run `docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile`.
6. Open `http://localhost:18080/ui/` for the workspace or `http://localhost:18080/api/health/` for the health check.

## Main API surfaces
- `/api/workouts/`
- `/api/workouts/{workout_id}`
- `/api/exercises/{exercise_name_canonical}/progress`
- `/api/analytics/weekly-load`
- `/api/measurements/`
- `POST /api/measurements/`
- `PATCH /api/measurements/{measurement_session_id}`
- `/api/measurements/latest`
- `/api/measurements/progress`
- `/api/measurements/overdue`
- `/api/profile/current/overview`
- `/api/profile/current/timeline`
- `/api/profile/current/progress-highlights`

## UI pages
- `/ui/` overview workspace with workout and body-progress cards
- `/ui/` measurements section with session list, detail panel, and create form
- `/ui/` progress section with simple body-measurement trend charts

## Modeling note

`body_weight` stays inside the `measurements` domain as a regular canonical measurement type. This keeps the RAW model, write API, ingestion, and marts consistent without introducing a separate weight subsystem too early.

## Docs
- `STARTUP_FLOW.md`
- `docs/PROJECT_OVERVIEW.md`
- `docs/DATA_CONTRACT.md`
- `docs/RUNBOOK_DOCKER.md`
- `docs/ROADMAP.md`
