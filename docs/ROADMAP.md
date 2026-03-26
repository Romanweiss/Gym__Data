# ROADMAP

## Stage 1

Foundation completed:

- Dockerized PostgreSQL, ClickHouse, backend
- deterministic SQL bootstrap
- ingestion of real workout JSON
- PostgreSQL RAW model
- ClickHouse MART model
- health and basic read endpoints
- runbook, smoke checks, and project structure docs

## Stage 1.1

Hardening and analytics layer completed in this step:

- workout detail endpoint from RAW
- per-workout analytical summary endpoint
- exercise progress endpoint
- weekly/cardio/recovery analytics endpoints
- reconciliation flow for source JSON vs flat JSONL vs PostgreSQL RAW
- stronger ingestion contract validation
- container-friendly tests for ingestion, reconciliation, and API detail
- clearer auth-ready and multi-tenant-ready extension points

## Stage 1.2

Logical next hardening step:

- detail endpoint filters and pagination helpers for future UI
- richer query params for workouts and exercises
- first metadata tables for clubs/users without enabling full auth flows
- scheduled ingestion runner and operational status endpoints
- CI wiring for tests plus reconciliation job
- mart-level regression checks against future dataset growth

## Stage 2

Platform boundaries without breaking the current data core:

- `clubs` for tenant boundaries
- `identity` for auth, sessions, and role contracts
- `trainers` and `clients` for actor ownership
- `programs` for plans and assignments
- `attendance` for check-ins and facility usage
- `memberships` and `payments` for subscription/billing boundaries

## Stage 3

Product-facing surfaces:

- admin/control panel
- trainer workspace
- client-facing application surfaces
- mobile-ready API expansion
- operational dashboards for workouts, attendance, and progress

## Stage 4

Realtime and scale-oriented additions:

- event-driven ingestion increments
- near-real-time progress/activity dashboards
- alerting and data-quality monitoring
- multi-club rollups and benchmark reporting

## Architectural principle

Keep these layers independently evolvable:

- source ingestion
- RAW storage
- analytical marts
- API read models
- future product domains

Every new stage should extend the current foundation, not collapse it into a single monolith.
