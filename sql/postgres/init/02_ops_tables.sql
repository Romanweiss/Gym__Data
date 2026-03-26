CREATE TABLE IF NOT EXISTS ops.ingestion_runs (
    run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    source_file_count INTEGER NOT NULL DEFAULT 0,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ops.ingestion_run_files (
    run_id UUID NOT NULL REFERENCES ops.ingestion_runs (run_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    workout_id TEXT NOT NULL,
    source_quality TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, file_path)
);

CREATE TABLE IF NOT EXISTS ops.ingestion_run_measurement_files (
    run_id UUID NOT NULL REFERENCES ops.ingestion_runs (run_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    measurement_session_id TEXT NOT NULL,
    subject_profile_id TEXT NOT NULL,
    source_quality TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, file_path)
);
