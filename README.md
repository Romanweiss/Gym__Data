# Gym__Data

Docker-first foundation for a workout analytics platform built around the existing `workouts/*.json` dataset.

## What is included
- PostgreSQL RAW layer for source-oriented workout facts
- ClickHouse MART layer for analytical rollups
- FastAPI backend with health, workout detail, exercise progress, and analytics endpoints
- Ingestion job that validates, loads, and reconciles the existing workout JSON files
- Runbook and roadmap for the next platform stages

## Quick start
1. Copy `.env.example` to `.env` if you want to override defaults.
2. Run `docker compose up -d --build`.
3. Run `docker compose --profile jobs run --rm ingestion`.
4. Optionally run `docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile`.
5. Open `http://localhost:18080/api/health/`.

## Docs
- `docs/PROJECT_OVERVIEW.md`
- `docs/DATA_CONTRACT.md`
- `docs/RUNBOOK_DOCKER.md`
- `docs/ROADMAP.md`
