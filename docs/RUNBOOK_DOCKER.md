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

## 4. Load the workout dataset

```powershell
docker compose --profile jobs run --rm ingestion
```

This validates `workouts/workouts/*.json`, loads PostgreSQL RAW tables, and rebuilds ClickHouse MART tables.

## 5. Basic API checks

- health: `http://localhost:18080/api/health/`
- workouts: `http://localhost:18080/api/workouts/`
- exercises: `http://localhost:18080/api/exercises/`
- summary: `http://localhost:18080/api/summary/`

## 6. Smoke check

```powershell
.\scripts\smoke_check.ps1
```

Or bootstrap everything in one go:

```powershell
.\scripts\smoke_check.ps1 -Bootstrap
```

## 7. Useful Compose commands

Show service status:

```powershell
docker compose ps
```

Tail backend logs:

```powershell
docker compose logs -f backend
```

Tail ingestion logs from the last run:

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

