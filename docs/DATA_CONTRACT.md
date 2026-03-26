# DATA CONTRACT

## Source of truth

- logical source layer: `workouts/*.json`
- current repository path: `workouts/workouts/*.json`

The `workouts/flat/*.jsonl` files are derived artifacts and are never treated as the primary source for workout facts.

Exception:

- `workouts/flat/exercise_dictionary.jsonl` is used as curated enrichment for aliases and muscle metadata that is not fully present in the nested workout source files

## Current dataset snapshot

Based on the current repository dataset:

- workouts: `43`
- exercise instances: `165`
- sets: `241`
- cardio segments: `45`
- recovery events: `61`
- detailed workouts: `11`
- partial raw workouts: `1`
- summary-only workouts: `31`

## RAW entities

### `raw.workouts`

Primary key:

- `workout_id`

Purpose:

- workout header
- source metadata
- preserved raw payload

### `raw.exercise_instances`

Primary key:

- `exercise_instance_id`

Foreign keys:

- `workout_id -> raw.workouts.workout_id`

Generated key format:

- `{workout_id}_ex_{sequence:02d}`

Important rule:

- generated ids are based on stable file sequence within one workout
- source `exercise.order` is preserved separately and may contain values such as `10.1` and `10.2`

### `raw.sets`

Logical key:

- `(exercise_instance_id, set_order)`

Foreign keys:

- `exercise_instance_id -> raw.exercise_instances.exercise_instance_id`
- `workout_id -> raw.workouts.workout_id`

Ordering rule:

- `set_order` must be dense `1..n` inside one exercise instance

### `raw.cardio_segments`

Logical key:

- `(workout_id, segment_order)`

Foreign key:

- `workout_id -> raw.workouts.workout_id`

Ordering rule:

- cardio `order` preserves original source numbering
- the sequence must stay ascending, but it is not required to be dense because numbering can be shared with exercises in the original notebook/source text

### `raw.recovery_events`

Logical key:

- `(workout_id, event_order)`

Foreign key:

- `workout_id -> raw.workouts.workout_id`

Ordering rule:

- recovery `order` preserves original source numbering
- the sequence must stay ascending, but it is not required to be dense

### `raw.exercise_dictionary`

Primary key:

- `exercise_name_canonical`

Purpose:

- stable canonical exercise dimension
- aliases
- muscle metadata
- load/category defaults

## Derived analytical layer

### `gym_data_mart.mart_workout_summary`

Per-workout summary with:

- exercise counts
- set counts
- total reps
- total volume
- cardio minutes
- recovery minutes
- set-level data presence flag

### `gym_data_mart.mart_exercise_daily`

Per workout and canonical exercise appearance with:

- category and load type
- set-level presence
- set/rep/volume totals
- max weight

### `gym_data_mart.mart_workout_detail_rollup`

Per-workout rollup for detail views and UI cards:

- exercise counts
- tracked exercise counts
- distinct canonical exercise counts
- bodyweight counts
- cardio/recovery counts and minutes

### `gym_data_mart.mart_exercise_progress`

Per workout and exercise instance progress rows with:

- source/display ordering
- split tags
- primary muscles
- set/reps/volume/max weight/max reps

### `gym_data_mart.mart_weekly_training_load`

Weekly load rollup with:

- workouts by source quality
- total exercise instances
- total sets
- total reps
- total volume
- cardio minutes
- recovery event counts and minutes

### `gym_data_mart.mart_cardio_summary`

Weekly cardio summary by:

- machine
- direction
- workout count
- segment count
- cardio minutes

### `gym_data_mart.mart_recovery_summary`

Weekly recovery summary by:

- event type
- workout count
- recovery event count
- recovery minutes

## Business rules enforced in ingestion

- canonical exercise names remain keyed by `exercise_name_canonical`
- spelling variants become aliases, not duplicate canonical rows
- exercise variation should live in attributes, not by inventing new canonical names
- bodyweight exercises must keep `weight_kg = 0` and `bodyweight = true`
- incomplete notation such as `125x` or `125х` must become `reps = 1` with `parse_note = reps_missing_defaulted_to_1`
- `source_quality` must be preserved at workout and exercise level
- `summary_only` workouts and exercises must not be treated as real set-level raw facts
- duplicate workout ids, exercise orders, set orders, cardio orders, and recovery orders are rejected
- source order for exercises/cardio/recovery must remain ascending

## Detail API contract

`GET /api/workouts/{workout_id}` is assembled from PostgreSQL RAW and returns a stable nested response shape:

- workout metadata
- `cardio_segments`
- `recovery_events`
- `exercise_instances`
- nested `sets`
- raw/source-quality fields
- canonical exercise names
- attributes and parse notes where present

This endpoint is intended to be UI/mobile-friendly without making ClickHouse the source of detail truth.

## Reconciliation contract

The reconciliation flow compares:

- source `workouts/workouts/*.json`
- derived `workouts/flat/*.jsonl`
- PostgreSQL `raw.*`

Minimum checks:

- entity counts
- missing rows
- orphan rows
- mismatched `workout_id`
- mismatched `exercise_instance_id`
- broken ordering
- duplicate logical rows

Serious mismatches return non-zero exit status.

## Loading strategy

Stage 1.1 still uses deterministic full refresh:

1. validate source JSON schema
2. validate data-contract rules
3. flatten nested documents
4. truncate and reload PostgreSQL RAW tables
5. rebuild ClickHouse MART tables
6. record the ingestion run
7. optionally reconcile source, flat, and RAW layers

This keeps the foundation simple, auditable, and safe to extend later.
