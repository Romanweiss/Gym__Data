# Body Measurements Source Domain

## What is here

- `measurements/*.json`: one JSON file per measurement session
- `flat/body_measurement_sessions.jsonl`: derived flat session rows
- `flat/body_measurement_values.jsonl`: derived flat measurement value rows
- `flat/measurement_type_dictionary.jsonl`: curated canonical measurement type dictionary
- `flat/subject_profiles.jsonl`: derived/default subject profile rows
- `schema/measurement_session.schema.json`: base schema for measurement session JSON

## Source-of-truth rules

- `measurements/measurements/*.json` is the source of truth for body measurement sessions
- one file represents one measurement session
- one session can contain multiple measurements taken under the same context
- measurements are a separate domain from workouts and must not be merged into workout facts
- `body_weight` is part of the measurements domain, not a special workout field

## Engineering rules

- canonical measurement type is resolved from `measurement_type_raw` through the measurement type dictionary
- units are stored explicitly; stage 1.2 supports canonical units only and does not do automatic unit conversion
- default recommendation cadence is 21 days and is configurable via environment
- measurement guidance is documented, but the system does not invent body composition metrics
- current stage assumes a default single-user subject profile while keeping future client/profile linkage explicit

## Recommended operational flow

1. Treat `measurements/measurements/*.json` as the source of truth
2. Validate against `schema/measurement_session.schema.json`
3. Flatten into session/value/profile rows
4. Load PostgreSQL RAW and ClickHouse MART
5. Reconcile source vs flat vs RAW
