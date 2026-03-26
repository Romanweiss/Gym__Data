# RUNBOOK DOCKER

## 1. Optional env file

Create `.env` only if you need to override defaults:

```powershell
Copy-Item .env.example .env
```

Do not overwrite an existing `.env` unless you intentionally want new values.

## 2. Verify host ports

```powershell
.\scripts\check_ports.ps1
```

Default host ports:

- backend: `18080`
- PostgreSQL: `55432`
- ClickHouse HTTP: `18123`
- ClickHouse native: `19000`

If one of them is occupied, update `.env` before startup.

## 3. Start infrastructure and backend

```powershell
docker compose up -d --build
```

## 4. Load the datasets

```powershell
docker compose --profile jobs run --rm ingestion
```

This command:

- validates `workouts/workouts/*.json`
- validates `measurements/measurements/*.json`
- applies data-contract checks
- loads PostgreSQL RAW tables for both domains
- rebuilds ClickHouse marts for both domains

Domain-specific ingestion commands:

```powershell
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main load-workouts
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main load-measurements
```

## 5. Reconcile source, flat, and RAW

```powershell
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile
```

Expected behavior:

- prints a text reconciliation report
- exits with code `0` on pass
- exits with non-zero code on serious mismatches

Domain-specific reconciliation commands:

```powershell
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile-workouts
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile-measurements
```

## 6. Run automated tests

Backend tests:

```powershell
docker compose run --rm --no-deps backend pytest
```

Ingestion tests:

```powershell
docker compose --profile jobs run --rm --no-deps ingestion python -m pytest
```

The ingestion tests use fixture copies of the real dataset bundled into the image, so they do not depend on host-mounted paths.

## 7. API checks

Core endpoints:

- health: `http://localhost:18080/api/health/`
- workouts list: `http://localhost:18080/api/workouts/`
- workout detail: `http://localhost:18080/api/workouts/{workout_id}`
- workout summary: `http://localhost:18080/api/workouts/{workout_id}/summary`
- exercises list: `http://localhost:18080/api/exercises/`
- exercise progress: `http://localhost:18080/api/exercises/{exercise_name_canonical}/progress`
- weekly analytics: `http://localhost:18080/api/analytics/weekly-load`
- cardio analytics: `http://localhost:18080/api/analytics/cardio`
- recovery analytics: `http://localhost:18080/api/analytics/recovery`
- measurement sessions: `http://localhost:18080/api/measurements/`
- measurement detail: `http://localhost:18080/api/measurements/{measurement_session_id}`
- latest measurements: `http://localhost:18080/api/measurements/latest`
- measurement progress: `http://localhost:18080/api/measurements/progress?measurement_type=waist`
- measurement overdue status: `http://localhost:18080/api/measurements/overdue`
- overall summary: `http://localhost:18080/api/summary/`

Example:

```powershell
Invoke-RestMethod http://localhost:18080/api/workouts/2026-03-08
Invoke-RestMethod http://localhost:18080/api/measurements/2026-03-01_morning
```

## 8. Smoke check

API smoke only:

```powershell
.\scripts\smoke_check.ps1
```

API smoke with reconciliation:

```powershell
.\scripts\smoke_check.ps1 -WithReconciliation
```

Bootstrap stack, load data, reconcile, and smoke-check:

```powershell
.\scripts\smoke_check.ps1 -Bootstrap
```

## 9. Useful Compose commands

Show service status:

```powershell
docker compose ps
```

Tail backend logs:

```powershell
docker compose logs -f backend
```

Run ingestion again:

```powershell
docker compose --profile jobs run --rm ingestion
```

Stop services:

```powershell
docker compose down
```

Reset containers and volumes:

```powershell
docker compose down -v
```

## 10. Troubleshooting notes

- if ports are busy, change `.env` first instead of editing compose defaults directly
- if ClickHouse volume already exists from an older build, ingestion still ensures stage-1.2 mart tables/views with `CREATE ... IF NOT EXISTS`
- if reconciliation fails, inspect the report before reloading; do not assume the flat layer or RAW layer is correct
- `MEASUREMENT_RECOMMENDATION_CADENCE_DAYS` and `DEFAULT_SUBJECT_PROFILE_ID` can be overridden in `.env` without changing code
