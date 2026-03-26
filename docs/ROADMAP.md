# ROADMAP

## Stage 1

Foundation delivered in this prompt:

- Dockerized PostgreSQL, ClickHouse, backend
- deterministic SQL bootstrap
- workout JSON ingestion with validation
- PostgreSQL raw model
- ClickHouse mart model
- health and read endpoints
- runbook and smoke checks

## Stage 2

Short next-step candidates:

- add workout detail endpoint and richer query filters
- add ingestion reconciliation against derived `flat/*.jsonl`
- add test suite for ingestion and API queries
- introduce scheduled ingestion/job runner
- add db-backed settings and basic admin observability

## Stage 3

Platform expansion without breaking the stage-1 core:

- `clubs` for multi-tenant boundaries
- `identity` for auth, sessions, and roles
- `trainers` and `clients` for domain ownership
- `programs` for coaching plans and assignments
- `attendance` for check-ins and class/gym presence
- `memberships` and `payments` for subscriptions and billing

## Stage 4

Product-facing surfaces:

- control panel / admin UI
- trainer workspace
- client-facing app surfaces
- mobile API surface
- near-real-time dashboards and progress feeds

## Architectural principle for future prompts

Keep source ingestion, raw storage, analytical marts, and product domains separately evolvable. New platform capabilities should extend the current foundation instead of folding everything into a single service or schema.

