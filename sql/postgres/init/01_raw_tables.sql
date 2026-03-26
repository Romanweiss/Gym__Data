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

CREATE TABLE IF NOT EXISTS raw.subject_profiles (
    subject_profile_id TEXT PRIMARY KEY,
    profile_kind TEXT NOT NULL DEFAULT 'person_placeholder',
    display_name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.measurement_type_dictionary (
    measurement_type_canonical TEXT PRIMARY KEY,
    aliases TEXT[] NOT NULL DEFAULT '{}',
    default_unit TEXT NOT NULL,
    category TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    value_kind TEXT NOT NULL CHECK (value_kind IN ('circumference', 'weight')),
    source_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.body_measurement_sessions (
    measurement_session_id TEXT PRIMARY KEY,
    subject_profile_id TEXT NOT NULL REFERENCES raw.subject_profiles (subject_profile_id) ON DELETE RESTRICT,
    measured_at TIMESTAMPTZ NOT NULL,
    measured_date DATE NOT NULL,
    source_type TEXT,
    source_quality TEXT NOT NULL CHECK (source_quality IN ('measured_direct', 'self_reported', 'imported_record')),
    context_time_of_day TEXT NOT NULL CHECK (context_time_of_day IN ('morning', 'unknown', 'other')),
    fasting_state BOOLEAN,
    before_training BOOLEAN,
    notes TEXT,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.body_measurement_values (
    measurement_value_id TEXT PRIMARY KEY,
    measurement_session_id TEXT NOT NULL REFERENCES raw.body_measurement_sessions (measurement_session_id) ON DELETE CASCADE,
    measurement_type_canonical TEXT NOT NULL REFERENCES raw.measurement_type_dictionary (measurement_type_canonical) ON DELETE RESTRICT,
    measurement_type_raw TEXT NOT NULL,
    value_numeric NUMERIC(10, 2) NOT NULL,
    unit TEXT NOT NULL,
    side_or_scope TEXT,
    raw_value TEXT,
    parse_note TEXT,
    notes TEXT,
    order_in_session INTEGER NOT NULL,
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (measurement_session_id, order_in_session)
);
