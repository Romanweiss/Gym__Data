# PROJECT OVERVIEW

## Goal of stage 1.1

`Gym__Data` stage 1.1 strengthens the already working foundation and makes it safer for analytics and future UI/mobile consumers.

Current scope:

- Docker-first runtime
- ingestion of real `workouts/workouts/*.json`
- PostgreSQL RAW layer
- ClickHouse MART layer
- FastAPI read API
- reconciliation between source, derived flat, and RAW
- tests, smoke checks, and extension-point documentation

Out of scope for this stage:

- full frontend
- mobile app
- full auth/session implementation
- billing engine
- realtime transport layer

## Architecture

```text
workouts/workouts/*.json
  -> JSON schema validation
  -> data-contract validation
  -> flattening / ingestion
  -> PostgreSQL raw.*
  -> ClickHouse gym_data_mart.mart_*
  -> FastAPI /api/*

workouts/flat/*.jsonl
  -> derived reference layer
  -> reconciliation target
```

## Why the split matters

- `workouts/workouts/*.json` remains the source of truth.
- PostgreSQL stores source-shaped facts close to the original workout structure.
- ClickHouse stores analytical rollups and progress views without polluting RAW with derived metrics.
- The backend reads PostgreSQL for workout detail and source-oriented endpoints, and ClickHouse for progress/load analytics.

## Stage 1.1 additions

- `GET /api/workouts/{workout_id}` returns a stable nested workout detail payload from RAW.
- `GET /api/workouts/{workout_id}/summary` returns per-workout analytical rollup from ClickHouse.
- `GET /api/exercises/{exercise_name_canonical}/progress` returns progress history and rollups for one canonical exercise.
- `GET /api/analytics/weekly-load`
- `GET /api/analytics/cardio`
- `GET /api/analytics/recovery`
- reconciliation CLI compares source JSON, derived `flat/*.jsonl`, and PostgreSQL RAW tables
- container-friendly tests cover ingestion, parsing contracts, detail API, and reconciliation

## Main components

- `compose.yaml`: runtime orchestration with safe host-port defaults
- `backend/`: FastAPI API service
- `ingestion/`: validation, flattening, load, and reconciliation logic
- `sql/postgres/init/`: deterministic PostgreSQL bootstrap
- `sql/clickhouse/init/`: deterministic ClickHouse bootstrap
- `scripts/check_ports.ps1`: verifies host ports before startup
- `scripts/smoke_check.ps1`: API smoke check with optional reconciliation

## Selected host ports

These defaults intentionally avoid the more common local ports that were already occupied during implementation.

- backend: `18080 -> 8000`
- PostgreSQL: `55432 -> 5432`
- ClickHouse HTTP: `18123 -> 8123`
- ClickHouse native: `19000 -> 9000`

## Bounded contexts

Current active contexts:

- `workouts`
- `exercises`
- `analytics`

Prepared extension points:

- `identity`
- `clubs`
- `trainers`
- `clients`
- `memberships`
- `payments`
- `attendance`
- `programs`

At this stage they are contracts/placeholders only. The project remains a single-user, single-tenant workout analytics core.

## Auth-ready and multi-tenant-ready posture

The codebase now keeps lightweight contracts for:

- actor/session scope
- tenant/club scope
- future bounded contexts in the package structure

This makes future auth and club expansion additive instead of forcing a rewrite of the current workout pipeline.
