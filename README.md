# Gym__Data

Docker-first foundation for a fitness analytics platform built around real `workouts/*.json` and `measurements/*.json` source datasets.

## What is included
- PostgreSQL RAW layer for source-oriented workout facts and body measurement sessions
- ClickHouse MART layer for workout and measurement analytics
- FastAPI backend with health, workout detail, exercise progress, measurement progress, and analytics endpoints
- Ingestion job that validates, loads, and reconciles the existing workout and measurement JSON files
- Runbook and roadmap for the next platform stages

## Quick start
1. Copy `.env.example` to `.env` if you want to override defaults.
2. Run `docker compose up -d --build`.
3. Run `docker compose --profile jobs run --rm ingestion`.
4. Optionally run `docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile`.
5. Open `http://localhost:18080/api/health/`.

## Main API surfaces
- `/api/workouts/`
- `/api/workouts/{workout_id}`
- `/api/exercises/{exercise_name_canonical}/progress`
- `/api/analytics/weekly-load`
- `/api/measurements/`
- `/api/measurements/latest`
- `/api/measurements/progress`
- `/api/measurements/overdue`

## Docs
- `docs/PROJECT_OVERVIEW.md`
- `docs/DATA_CONTRACT.md`
- `docs/RUNBOOK_DOCKER.md`
- `docs/ROADMAP.md`
