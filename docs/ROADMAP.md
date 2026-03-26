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

Body progress foundation completed in this step:

- body measurement source-of-truth structure
- PostgreSQL RAW tables for subject profiles, measurement sessions, and measurement values
- canonical measurement type dictionary
- ingestion, validation, and reconciliation for measurements
- ClickHouse marts for latest values, deltas, overdue cadence, and workout-activity bridge
- measurement API endpoints for detail, latest values, progress, and overdue recommendation
- auth-ready subject/profile extension point without enabling full auth flows
- container-friendly tests for measurement schema, normalization, analytics, API, and reconciliation

## Stage 1.3

Profile-centric progress workspace completed in this step:

- `POST /api/measurements/` write path with safe validation and id generation
- `PATCH /api/measurements/{measurement_session_id}` for source-oriented updates
- unified profile overview, timeline, and progress highlights endpoints
- embedded MVP control panel for overview, measurements, and progress charts
- body-progress write/read contracts that keep `body_weight` inside the unified measurements domain
- backend and ingestion tests covering write flow, profile endpoints, and UI shell availability

## Stage 1.4

Logical next hardening step:

- CI wiring for backend tests, ingestion tests, reconciliation, and smoke checks
- operational status endpoints and ingestion-run visibility
- safe delete/archive strategy for mutable measurement sessions
- richer filters and pagination helpers for workouts, exercises, measurements, and profile timeline
- first optional reminders/notification contracts without implementing the delivery engine

## Stage 2

Platform boundaries without breaking the current data core:

- `clubs` for tenant boundaries
- `identity` for auth, sessions, and role contracts
- `trainers` and `clients` for actor ownership
- per-client body progress ownership and trainer-visible progress history
- `programs` for plans and assignments
- `attendance` for check-ins and facility usage
- `memberships` and `payments` for subscription/billing boundaries

## Stage 3

Product-facing surfaces:

- admin/control panel
- trainer workspace
- client-facing application surfaces
- mobile-ready API expansion
- operational dashboards for workouts, body progress, attendance, and overall progress

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
