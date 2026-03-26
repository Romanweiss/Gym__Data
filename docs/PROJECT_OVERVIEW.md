# PROJECT OVERVIEW

## Goal of stage 1

`Gym__Data` stage 1 is the data/backend foundation for a future workout analytics platform. It is intentionally narrow:

- Docker-first runtime
- ingestion of the existing workout dataset
- PostgreSQL RAW layer
- ClickHouse MART layer
- backend API skeleton
- docs, runbook, and extension points for future product growth

This stage does not attempt to implement the future B2B/B2C platform end-to-end.

## Current architecture

```text
workouts/workouts/*.json
  -> schema validation + contract checks
  -> flattening / ingestion
  -> PostgreSQL raw.*
  -> ClickHouse gym_data_mart.mart_*
  -> FastAPI /api/*
```

## Why this split

- `workouts/workouts/*.json` is the source of truth in the current repository layout.
- PostgreSQL keeps source-oriented facts close to the original structure.
- ClickHouse stores analytical rollups without polluting the raw layer with derived metrics.
- The backend reads from PostgreSQL for operational/source-shaped endpoints and from ClickHouse for analytical summaries.

## Main components

- `compose.yaml`: runtime orchestration
- `backend/`: FastAPI API service
- `ingestion/`: validation + load job
- `sql/postgres/init/`: deterministic PostgreSQL bootstrap
- `sql/clickhouse/init/`: deterministic ClickHouse bootstrap
- `scripts/check_ports.ps1`: verifies the selected host ports are free
- `scripts/smoke_check.ps1`: minimal end-to-end smoke check

## Selected host ports

These defaults were chosen because common local ports were already occupied on the machine during implementation.

- backend: `18080 -> 8000`
- PostgreSQL: `55432 -> 5432`
- ClickHouse HTTP: `18123 -> 8123`
- ClickHouse native: `19000 -> 9000`

## Future extension points

The codebase already reserves bounded-context space for:

- `identity`
- `clubs`
- `trainers`
- `clients`
- `memberships`
- `payments`
- `attendance`
- `programs`

They are placeholders only at this stage. The current implementation remains focused on workouts, exercises, and analytics.

