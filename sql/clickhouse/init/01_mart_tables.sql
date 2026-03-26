CREATE TABLE IF NOT EXISTS gym_data_mart.mart_workout_summary
(
    workout_id String,
    workout_date Date,
    session_sequence UInt16,
    source_quality LowCardinality(String),
    title_raw String,
    split_normalized Array(String),
    exercise_count UInt32,
    set_tracked_exercise_count UInt32,
    set_count UInt32,
    total_reps UInt32,
    total_volume_kg Float64,
    cardio_minutes UInt32,
    recovery_minutes UInt32,
    has_set_level_data UInt8
)
ENGINE = MergeTree
ORDER BY (workout_date, workout_id);

CREATE TABLE IF NOT EXISTS gym_data_mart.mart_exercise_daily
(
    workout_date Date,
    workout_id String,
    session_sequence UInt16,
    exercise_name_canonical String,
    category LowCardinality(String),
    load_type LowCardinality(String),
    source_quality LowCardinality(String),
    bodyweight UInt8,
    workout_appearance UInt8,
    has_set_level_data UInt8,
    set_count UInt32,
    total_reps UInt32,
    total_volume_kg Float64,
    max_weight_kg Float64
)
ENGINE = MergeTree
ORDER BY (exercise_name_canonical, workout_date, workout_id);

CREATE VIEW IF NOT EXISTS gym_data_mart.v_daily_workout_rollup AS
SELECT
    workout_date,
    count() AS workouts_total,
    sum(set_count) AS set_count,
    sum(total_reps) AS total_reps,
    round(sum(total_volume_kg), 2) AS total_volume_kg,
    sum(cardio_minutes) AS cardio_minutes,
    sum(recovery_minutes) AS recovery_minutes
FROM gym_data_mart.mart_workout_summary
GROUP BY workout_date;

CREATE VIEW IF NOT EXISTS gym_data_mart.v_exercise_rollup AS
SELECT
    exercise_name_canonical,
    any(category) AS category,
    any(load_type) AS load_type,
    count() AS workout_appearances,
    sum(has_set_level_data) AS tracked_workout_appearances,
    sum(set_count) AS set_count,
    sum(total_reps) AS total_reps,
    round(sum(total_volume_kg), 2) AS total_volume_kg,
    max(max_weight_kg) AS max_weight_kg,
    max(workout_date) AS last_seen_date
FROM gym_data_mart.mart_exercise_daily
GROUP BY exercise_name_canonical;

CREATE TABLE IF NOT EXISTS gym_data_mart.mart_workout_detail_rollup
(
    workout_id String,
    workout_date Date,
    session_sequence UInt16,
    source_quality LowCardinality(String),
    title_raw String,
    split_normalized Array(String),
    exercise_count UInt32,
    tracked_exercise_count UInt32,
    distinct_canonical_exercise_count UInt32,
    bodyweight_exercise_count UInt32,
    bodyweight_set_count UInt32,
    set_count UInt32,
    total_reps UInt32,
    total_volume_kg Float64,
    cardio_segments_count UInt32,
    cardio_minutes UInt32,
    recovery_events_count UInt32,
    recovery_minutes UInt32
)
ENGINE = MergeTree
ORDER BY (workout_date, workout_id);

CREATE TABLE IF NOT EXISTS gym_data_mart.mart_exercise_progress
(
    workout_date Date,
    workout_id String,
    session_sequence UInt16,
    exercise_instance_id String,
    display_order UInt16,
    exercise_order Float64,
    exercise_name_canonical String,
    exercise_name_raw String,
    category LowCardinality(String),
    load_type LowCardinality(String),
    source_quality LowCardinality(String),
    bodyweight UInt8,
    split_normalized Array(String),
    primary_muscles Array(String),
    set_count UInt32,
    total_reps UInt32,
    total_volume_kg Float64,
    max_weight_kg Float64,
    max_reps_in_set UInt32
)
ENGINE = MergeTree
ORDER BY (exercise_name_canonical, workout_date, workout_id, display_order);

CREATE TABLE IF NOT EXISTS gym_data_mart.mart_weekly_training_load
(
    week_start Date,
    workouts_total UInt32,
    raw_detailed_workouts UInt32,
    partial_raw_workouts UInt32,
    summary_only_workouts UInt32,
    exercise_instances_total UInt32,
    set_count UInt32,
    total_reps UInt32,
    total_volume_kg Float64,
    cardio_minutes UInt32,
    recovery_events_total UInt32,
    recovery_minutes UInt32
)
ENGINE = MergeTree
ORDER BY week_start;

CREATE TABLE IF NOT EXISTS gym_data_mart.mart_cardio_summary
(
    week_start Date,
    machine String,
    direction String,
    workouts_total UInt32,
    segments_total UInt32,
    cardio_minutes UInt32
)
ENGINE = MergeTree
ORDER BY (week_start, machine, direction);

CREATE TABLE IF NOT EXISTS gym_data_mart.mart_recovery_summary
(
    week_start Date,
    event_type String,
    workouts_total UInt32,
    recovery_events_total UInt32,
    recovery_minutes UInt32
)
ENGINE = MergeTree
ORDER BY (week_start, event_type);

CREATE VIEW IF NOT EXISTS gym_data_mart.v_exercise_progress_rollup AS
SELECT
    progress.exercise_name_canonical,
    any(progress.category) AS category,
    any(progress.load_type) AS load_type,
    any(progress.primary_muscles) AS primary_muscles,
    count() AS workout_appearances,
    sum(if(progress.set_count > 0, 1, 0)) AS tracked_workout_appearances,
    sum(progress.set_count) AS set_count,
    sum(progress.total_reps) AS total_reps,
    round(sum(progress.total_volume_kg), 2) AS total_volume_kg,
    max(progress.max_weight_kg) AS max_weight_kg,
    max(progress.max_reps_in_set) AS max_reps_in_set,
    min(progress.workout_date) AS first_performed_date,
    max(progress.workout_date) AS last_performed_date
FROM gym_data_mart.mart_exercise_progress AS progress
GROUP BY progress.exercise_name_canonical;
