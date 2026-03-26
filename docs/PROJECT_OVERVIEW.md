# PROJECT OVERVIEW

## Goal of stage 1.2

`Gym__Data` stage 1.2 keeps the Stage 1.1 workout foundation intact and adds a first-class body progress domain that is already useful in single-user mode and ready for future client/trainer/club expansion.

Current scope:

- Docker-first runtime
- ingestion of real `workouts/workouts/*.json`
- ingestion of real `measurements/measurements/*.json`
- PostgreSQL RAW layer
- ClickHouse MART layer
- FastAPI read API
- reconciliation between source, derived flat, and RAW for both domains
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

measurements/measurements/*.json
  -> JSON schema validation
  -> canonical measurement normalization
  -> flattening / ingestion
  -> PostgreSQL raw.*
  -> ClickHouse gym_data_mart.mart_measurement_*
  -> FastAPI /api/measurements/*

workouts/flat/*.jsonl
  -> derived reference layer
  -> reconciliation target

measurements/flat/*.jsonl
  -> derived reference layer
  -> reconciliation target
```

## Why the split matters

- `workouts/workouts/*.json` remains the source of truth.
- `measurements/measurements/*.json` remains the source of truth for body measurement sessions.
- PostgreSQL stores source-shaped facts close to the original workout structure.
- ClickHouse stores analytical rollups and progress views without polluting RAW with derived metrics.
- Measurements stay separate from workouts in RAW, but analytical bridges connect them in MART where that is grounded in real facts.
- The backend reads PostgreSQL for workout and measurement detail, and ClickHouse for progress/load analytics.

## Stage 1.2 additions

- `GET /api/workouts/{workout_id}` returns a stable nested workout detail payload from RAW.
- `GET /api/workouts/{workout_id}/summary` returns per-workout analytical rollup from ClickHouse.
- `GET /api/exercises/{exercise_name_canonical}/progress` returns progress history and rollups for one canonical exercise.
- `GET /api/analytics/weekly-load`
- `GET /api/analytics/cardio`
- `GET /api/analytics/recovery`
- `GET /api/measurements/` returns measurement sessions with filters.
- `GET /api/measurements/{measurement_session_id}` returns a stable nested body-measurement session payload from RAW.
- `GET /api/measurements/latest` returns the latest known value per canonical measurement type.
- `GET /api/measurements/progress` returns a timeline with deltas and training-activity bridge metrics.
- `GET /api/measurements/overdue` returns cadence-aware recommendation status.
- reconciliation CLI compares source JSON, derived `flat/*.jsonl`, and PostgreSQL RAW tables
- container-friendly tests cover ingestion, parsing contracts, detail API, reconciliation, measurement analytics, and overdue logic

## Main components

- `compose.yaml`: runtime orchestration with safe host-port defaults
- `backend/`: FastAPI API service
- `ingestion/`: validation, flattening, load, and reconciliation logic
- `measurements/`: source-of-truth measurement files, schema, and flat reference layer
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
- `measurements`

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
- subject/profile ownership for progress data
- future measurement photo references and cadence-policy contracts
- future bounded contexts in the package structure

Stage 1.2 introduces `raw.subject_profiles` as a minimal, auth-free placeholder so body progress can belong to a future person/client profile without hardcoding the whole system into permanent single-user mode.

This keeps future auth, client, trainer, and club expansion additive instead of forcing a rewrite of the current data core.
