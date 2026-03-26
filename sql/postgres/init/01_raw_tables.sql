CREATE TABLE IF NOT EXISTS raw.workouts (
    workout_id TEXT PRIMARY KEY,
    workout_date DATE NOT NULL,
    session_sequence INTEGER NOT NULL DEFAULT 1,
    title_raw TEXT NOT NULL,
    split_raw TEXT[] NOT NULL DEFAULT '{}',
    split_normalized TEXT[] NOT NULL DEFAULT '{}',
    source_type TEXT,
    source_quality TEXT NOT NULL CHECK (source_quality IN ('raw_detailed', 'partial_raw', 'summary_only')),
    source_text TEXT,
    notes TEXT,
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.exercise_instances (
    exercise_instance_id TEXT PRIMARY KEY,
    workout_id TEXT NOT NULL REFERENCES raw.workouts (workout_id) ON DELETE CASCADE,
    exercise_order NUMERIC(10, 2) NOT NULL,
    exercise_name_raw TEXT NOT NULL,
    exercise_name_canonical TEXT NOT NULL,
    category TEXT NOT NULL,
    load_type TEXT NOT NULL,
    bodyweight BOOLEAN NOT NULL DEFAULT FALSE,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_sets_text TEXT,
    notes TEXT,
    source_quality TEXT NOT NULL CHECK (source_quality IN ('raw_detailed', 'partial_raw', 'summary_only')),
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workout_id, exercise_order)
);

CREATE TABLE IF NOT EXISTS raw.sets (
    exercise_instance_id TEXT NOT NULL REFERENCES raw.exercise_instances (exercise_instance_id) ON DELETE CASCADE,
    workout_id TEXT NOT NULL REFERENCES raw.workouts (workout_id) ON DELETE CASCADE,
    set_order INTEGER NOT NULL,
    weight_kg NUMERIC(10, 2) NOT NULL,
    reps INTEGER NOT NULL,
    raw_value TEXT,
    parse_note TEXT,
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (exercise_instance_id, set_order)
);

CREATE TABLE IF NOT EXISTS raw.cardio_segments (
    workout_id TEXT NOT NULL REFERENCES raw.workouts (workout_id) ON DELETE CASCADE,
    segment_order INTEGER NOT NULL,
    machine TEXT NOT NULL,
    direction TEXT,
    duration_min INTEGER,
    notes TEXT,
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workout_id, segment_order)
);

CREATE TABLE IF NOT EXISTS raw.recovery_events (
    workout_id TEXT NOT NULL REFERENCES raw.workouts (workout_id) ON DELETE CASCADE,
    event_order INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    duration_min INTEGER,
    notes TEXT,
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workout_id, event_order)
);

CREATE TABLE IF NOT EXISTS raw.exercise_dictionary (
    exercise_name_canonical TEXT PRIMARY KEY,
    aliases TEXT[] NOT NULL DEFAULT '{}',
    category TEXT NOT NULL,
    load_type TEXT NOT NULL,
    bodyweight_default BOOLEAN NOT NULL DEFAULT FALSE,
    primary_muscles TEXT[] NOT NULL DEFAULT '{}',
    source_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
