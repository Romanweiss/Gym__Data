# DATA CONTRACT

## Source of truth

- workout source layer: `workouts/*.json`
- current workout repository path: `workouts/workouts/*.json`
- measurement source layer: `measurements/*.json`
- current measurement repository path: `measurements/measurements/*.json`

The `workouts/flat/*.jsonl` and `measurements/flat/*.jsonl` files are derived artifacts and are never treated as the primary source for facts.

Exception:

- `workouts/flat/exercise_dictionary.jsonl` is used as curated enrichment for aliases and muscle metadata that is not fully present in the nested workout source files
- `measurements/flat/measurement_type_dictionary.jsonl` is used as curated enrichment for canonical measurement aliases, units, and categories

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
- subject profiles: `1`
- measurement sessions: `4`
- measurement values: `40`
- canonical measurement types: `10`

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

### `raw.subject_profiles`

Primary key:

- `subject_profile_id`

Purpose:

- minimal subject placeholder for future users/clients
- default single-user ownership anchor for measurements
- migration-safe extension point for auth and multi-tenant growth

### `raw.measurement_type_dictionary`

Primary key:

- `measurement_type_canonical`

Purpose:

- stable canonical measurement dimension
- aliases and normalization rules
- default unit
- category and sort order
- `value_kind` such as `circumference` or `weight`

### `raw.body_measurement_sessions`

Primary key:

- `measurement_session_id`

Foreign keys:

- `subject_profile_id -> raw.subject_profiles.subject_profile_id`

Purpose:

- one session = one point-in-time body measurement event
- preserves context such as `measured_at`, `context_time_of_day`, `fasting_state`, and `before_training`
- preserves `source_type` and `source_quality`

### `raw.body_measurement_values`

Primary key:

- `measurement_value_id`

Foreign keys:

- `measurement_session_id -> raw.body_measurement_sessions.measurement_session_id`
- `measurement_type_canonical -> raw.measurement_type_dictionary.measurement_type_canonical`

Logical key:

- `(measurement_session_id, order_in_session)`

Purpose:

- one row per measurement value inside a session
- keeps canonical type, raw type, numeric value, unit, notes, parse note, and optional side/scope
- supports body weight without inventing extra body composition metrics

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

### `gym_data_mart.mart_measurement_progress`

Timeline of measurement values with:

- subject profile
- canonical measurement type
- previous value and delta
- days since previous measurement
- workouts/cardio/recovery activity between comparable measurement sessions

### `gym_data_mart.mart_measurement_deltas`

Value-to-previous comparison layer with:

- current value
- previous value
- delta
- days since previous comparable measurement

### `gym_data_mart.mart_measurement_latest`

Latest known value per measurement type with:

- latest session/date
- previous session/date
- latest value
- delta to previous

### `gym_data_mart.mart_measurement_overdue`

Cadence/recommendation layer with:

- last measurement date
- days since last measurement
- workouts since last measurement
- recommendation status and reason

### `gym_data_mart.mart_measurement_vs_workout_activity`

Analytical bridge between measurements and workout history with:

- workouts between measurement sessions
- set/rep/volume totals where real raw facts exist
- cardio and recovery minutes
- last workout before each measurement session

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
- canonical measurement types remain keyed by `measurement_type_canonical`
- spelling variants such as localized aliases must normalize to canonical measurement types, not create duplicates
- measurement units must stay explicit and comparable; unsupported conversions are rejected instead of guessed
- missing measurement unit may default from the canonical dictionary only when the type is unambiguous, and the loader must preserve a parse note
- `body_weight` is a first-class measurement type, not a special side channel
- no body composition metrics are invented beyond the actual recorded data
- default measurement cadence is configurable and documented, not treated as medical truth

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

`GET /api/measurements/{measurement_session_id}` is assembled from PostgreSQL RAW and returns:

- measurement session metadata
- subject profile placeholder
- stable ordered measurement values
- canonical measurement names
- raw names, units, parse notes, and quality/context fields

`GET /api/measurements/latest`, `GET /api/measurements/progress`, and `GET /api/measurements/overdue` read from ClickHouse or RAW according to responsibility:

- PostgreSQL for source-oriented detail and recommendation context
- ClickHouse for latest/progress analytical views

## Reconciliation contract

The reconciliation flow compares:

- source `workouts/workouts/*.json`
- derived `workouts/flat/*.jsonl`
- PostgreSQL `raw.*`
- source `measurements/measurements/*.json`
- derived `measurements/flat/*.jsonl`
- PostgreSQL measurement raw tables

Minimum checks:

- entity counts
- missing rows
- orphan rows
- mismatched `workout_id`
- mismatched `exercise_instance_id`
- broken ordering
- duplicate logical rows
- mismatched `measurement_session_id`
- broken measurement ordering
- duplicate measurement logical rows

Serious mismatches return non-zero exit status.

## Loading strategy

Stage 1.2 still uses deterministic full refresh:

1. validate source JSON schema
2. validate data-contract rules
3. flatten workout and measurement documents in parallel domains
4. truncate and reload PostgreSQL RAW tables
5. rebuild ClickHouse MART tables
6. record the ingestion run
7. optionally reconcile source, flat, and RAW layers for both domains

This keeps the foundation simple, auditable, and safe to extend later.
