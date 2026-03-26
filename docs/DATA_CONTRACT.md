# DATA CONTRACT

## Source of truth

- logical source layer: `workouts/*.json`
- current repository path: `workouts/workouts/*.json`

The `flat/*.jsonl` files remain derived artifacts. In stage 1 they are not treated as the primary source, with one exception:

- `workouts/flat/exercise_dictionary.jsonl` is used as curated dimension enrichment for the exercise dictionary because it contains alias and muscle metadata not fully present in the nested workout source files.

## Current dataset snapshot

Based on `workouts/manifest.json`:

- workouts: `43`
- detailed workouts: `11`
- partial raw workouts: `1`
- summary-only workouts: `31`
- set rows: `241`
- exercise instances: `165`
- cardio segments: `45`
- recovery events: `61`

## RAW tables

### `raw.workouts`

Primary key:
- `workout_id`

Purpose:
- source-oriented workout header and raw payload preservation

### `raw.exercise_instances`

Primary key:
- `exercise_instance_id`

Foreign keys:
- `workout_id -> raw.workouts.workout_id`

Generated key format:
- `{workout_id}_ex_{sequence:02d}`

Notes:
- source `exercise.order` is preserved separately and may contain decimal-like values such as `10.1` and `10.2`
- the generated primary key is based on stable sequence within the workout file, not on the source order numeric value

### `raw.sets`

Primary key:
- `(exercise_instance_id, set_order)`

Foreign keys:
- `exercise_instance_id -> raw.exercise_instances.exercise_instance_id`
- `workout_id -> raw.workouts.workout_id`

### `raw.cardio_segments`

Primary key:
- `(workout_id, segment_order)`

Foreign keys:
- `workout_id -> raw.workouts.workout_id`

### `raw.recovery_events`

Primary key:
- `(workout_id, event_order)`

Foreign keys:
- `workout_id -> raw.workouts.workout_id`

### `raw.exercise_dictionary`

Primary key:
- `exercise_name_canonical`

Purpose:
- stable canonical exercise dimension with aliases and enrichment

## MART tables

### `gym_data_mart.mart_workout_summary`

One row per workout with transparent analytical fields:

- exercise counts
- set counts
- total reps
- total volume
- cardio minutes
- recovery minutes
- presence of set-level data

### `gym_data_mart.mart_exercise_daily`

One row per workout/exercise instance with:

- category and load type
- workout appearance
- tracked set presence
- reps, volume, and max weight

## Business rules enforced in ingestion

- canonical exercise names remain keyed by `exercise_name_canonical`
- spelling variants are merged into aliases, not new canonical keys
- bodyweight exercises must keep `weight_kg = 0`
- `parse_note = reps_missing_defaulted_to_1` must preserve `reps = 1`
- `summary_only` workouts cannot contain set-level raw facts
- duplicate workout ids, exercise orders, set orders, cardio orders, and recovery orders are rejected

## Loading strategy

Stage 1 uses a deterministic full refresh:

1. validate all source workout JSON documents
2. flatten them into relational rows
3. truncate and reload PostgreSQL RAW tables
4. rebuild ClickHouse MART tables
5. record the run in `ops.ingestion_runs`

This is deliberate for correctness and simplicity in the foundation stage.
