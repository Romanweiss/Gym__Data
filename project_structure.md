# Project Structure

Current repository structure for `Gym__Data`.

Note: `.git/` is intentionally omitted.

```text
Gym__Data/
|-- .env.example
|-- .gitignore
|-- compose.yaml
|-- README.md
|-- project_structure.md
|-- backend/
|   |-- Dockerfile
|   |-- pyproject.toml
|   `-- app/
|       |-- main.py
|       |-- __init__.py
|       |-- api/
|       |   |-- router.py
|       |   |-- __init__.py
|       |   `-- routes/
|       |       |-- exercises.py
|       |       |-- health.py
|       |       |-- summary.py
|       |       |-- workouts.py
|       |       `-- __init__.py
|       |-- core/
|       |   |-- config.py
|       |   `-- __init__.py
|       |-- db/
|       |   |-- clickhouse.py
|       |   |-- postgres.py
|       |   `-- __init__.py
|       |-- domain/
|       |   |-- context_registry.py
|       |   |-- __init__.py
|       |   |-- analytics/
|       |   |   `-- __init__.py
|       |   |-- attendance/
|       |   |   `-- __init__.py
|       |   |-- clients/
|       |   |   `-- __init__.py
|       |   |-- clubs/
|       |   |   `-- __init__.py
|       |   |-- exercises/
|       |   |   `-- __init__.py
|       |   |-- identity/
|       |   |   `-- __init__.py
|       |   |-- memberships/
|       |   |   `-- __init__.py
|       |   |-- payments/
|       |   |   `-- __init__.py
|       |   |-- programs/
|       |   |   `-- __init__.py
|       |   |-- trainers/
|       |   |   `-- __init__.py
|       |   `-- workouts/
|       |       `-- __init__.py
|       `-- services/
|           |-- exercise_service.py
|           |-- health_service.py
|           |-- serialization.py
|           |-- summary_service.py
|           |-- workout_service.py
|           `-- __init__.py
|-- data/
|   `-- README.md
|-- docs/
|   |-- DATA_CONTRACT.md
|   |-- PROJECT_OVERVIEW.md
|   |-- ROADMAP.md
|   `-- RUNBOOK_DOCKER.md
|-- ingestion/
|   |-- Dockerfile
|   |-- pyproject.toml
|   `-- gym_data_ingestion/
|       |-- models.py
|       |-- settings.py
|       |-- __init__.py
|       |-- cli/
|       |   |-- main.py
|       |   `-- __init__.py
|       |-- loaders/
|       |   |-- clickhouse.py
|       |   |-- postgres.py
|       |   `-- __init__.py
|       `-- validation/
|           |-- schema.py
|           `-- __init__.py
|-- scripts/
|   |-- check_ports.ps1
|   `-- smoke_check.ps1
|-- sql/
|   |-- clickhouse/
|   |   `-- init/
|   |       |-- 00_database.sql
|   |       `-- 01_mart_tables.sql
|   `-- postgres/
|       `-- init/
|           |-- 00_schemas.sql
|           |-- 01_raw_tables.sql
|           |-- 02_ops_tables.sql
|           `-- 03_indexes.sql
`-- workouts/
    |-- index.json
    |-- manifest.json
    |-- README.md
    |-- flat/
    |   |-- cardio_segments.jsonl
    |   |-- exercise_dictionary.jsonl
    |   |-- exercise_instances.jsonl
    |   |-- recovery_events.jsonl
    |   |-- sets.jsonl
    |   `-- workouts.jsonl
    |-- schema/
    |   `-- workout.schema.json
    `-- workouts/
        |-- 2026-01-09.json
        |-- 2026-01-11_a.json
        |-- 2026-01-11_b.json
        |-- 2026-01-13.json
        |-- 2026-01-16.json
        |-- 2026-01-18.json
        |-- 2026-01-19.json
        |-- 2026-01-20.json
        |-- 2026-01-24.json
        |-- 2026-01-25.json
        |-- 2026-01-28.json
        |-- 2026-01-30.json
        |-- 2026-01-31.json
        |-- 2026-02-01.json
        |-- 2026-02-02.json
        |-- 2026-02-03.json
        |-- 2026-02-05.json
        |-- 2026-02-07.json
        |-- 2026-02-09.json
        |-- 2026-02-11.json
        |-- 2026-02-12.json
        |-- 2026-02-13.json
        |-- 2026-02-15.json
        |-- 2026-02-16.json
        |-- 2026-02-19.json
        |-- 2026-02-22.json
        |-- 2026-02-24.json
        |-- 2026-02-25.json
        |-- 2026-02-27.json
        |-- 2026-03-01.json
        |-- 2026-03-05.json
        |-- 2026-03-07.json
        |-- 2026-03-08.json
        |-- 2026-03-10.json
        |-- 2026-03-11.json
        |-- 2026-03-13.json
        |-- 2026-03-14.json
        |-- 2026-03-15.json
        |-- 2026-03-17.json
        |-- 2026-03-19.json
        |-- 2026-03-21.json
        |-- 2026-03-23.json
        `-- 2026-03-25.json
```
