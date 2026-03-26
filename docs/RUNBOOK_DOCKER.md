# RUNBOOK DOCKER

## 0. Stop previous Gym__Data containers if needed

If the project was already running before, stop only the current `Gym__Data` stack first:

```powershell
docker compose down
```

This command affects only the Compose project from the current repository root and does not stop unrelated Docker projects.

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
docker compose --profile jobs run --rm --build ingestion
```

This command:

- validates `workouts/workouts/*.json`
- validates `measurements/measurements/*.json`
- applies data-contract checks
- loads PostgreSQL RAW tables for both domains
- rebuilds ClickHouse marts for both domains

Domain-specific ingestion commands:

```powershell
docker compose --profile jobs run --rm --build ingestion python -m gym_data_ingestion.cli.main load-workouts
docker compose --profile jobs run --rm --build ingestion python -m gym_data_ingestion.cli.main load-measurements
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
- create measurement session: `POST http://localhost:18080/api/measurements/`
- update measurement session: `PATCH http://localhost:18080/api/measurements/{measurement_session_id}`
- measurement detail: `http://localhost:18080/api/measurements/{measurement_session_id}`
- latest measurements: `http://localhost:18080/api/measurements/latest`
- measurement progress: `http://localhost:18080/api/measurements/progress?measurement_type=waist`
- measurement overdue status: `http://localhost:18080/api/measurements/overdue`
- profile overview: `http://localhost:18080/api/profile/current/overview`
- profile timeline: `http://localhost:18080/api/profile/current/timeline`
- profile progress highlights: `http://localhost:18080/api/profile/current/progress-highlights`
- embedded UI: `http://localhost:18080/ui/`
- overall summary: `http://localhost:18080/api/summary/`

Example:

```powershell
Invoke-RestMethod http://localhost:18080/api/workouts/2026-03-08
Invoke-RestMethod http://localhost:18080/api/measurements/2026-03-01_morning
Invoke-RestMethod http://localhost:18080/api/profile/current/overview
Start-Process http://localhost:18080/ui/
```

Create a new measurement session:

```powershell
$payload = @{
    measured_at = "2026-03-27T08:00:00"
    measured_date = "2026-03-27"
    context_time_of_day = "morning"
    fasting_state = $true
    before_training = $true
    notes = "Stage 1.3 API write example"
    measurements = @(
        @{ measurement_type = "body_weight"; value_numeric = 92.4; unit = "kg" }
        @{ measurement_type = "waist"; value_numeric = 92.0; unit = "cm" }
        @{ measurement_type = "chest"; value_numeric = 108.8; unit = "cm" }
    )
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:18080/api/measurements/ `
    -ContentType "application/json" `
    -Body $payload
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
- if ClickHouse volume already exists from an older build, ingestion still ensures stage-1.3 mart tables/views with `CREATE ... IF NOT EXISTS`
- if reconciliation fails, inspect the report before reloading; do not assume the flat layer or RAW layer is correct
- `reconcile` only compares layers; it does not rebuild or reload them
- if code changed in `ingestion/`, reload data with a fresh ingestion image before re-running reconcile:
  `docker compose --profile jobs run --rm --build ingestion`
- `MEASUREMENT_RECOMMENDATION_CADENCE_DAYS` and `DEFAULT_SUBJECT_PROFILE_ID` can be overridden in `.env` without changing code
- the embedded UI is served by the backend service, so there is no separate frontend container or host port in stage 1.3
