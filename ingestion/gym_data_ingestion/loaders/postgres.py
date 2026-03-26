from typing import Any
from uuid import UUID

from psycopg import connect
from psycopg.types.json import Jsonb

from gym_data_ingestion.measurement_models import MeasurementFlattenedData
from gym_data_ingestion.models import FlattenedData

POSTGRES_STAGE_1_2_DDL = (
    """
    CREATE TABLE IF NOT EXISTS raw.subject_profiles (
        subject_profile_id TEXT PRIMARY KEY,
        profile_kind TEXT NOT NULL DEFAULT 'person_placeholder',
        display_name TEXT NOT NULL,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        notes TEXT,
        source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw.measurement_type_dictionary (
        measurement_type_canonical TEXT PRIMARY KEY,
        aliases TEXT[] NOT NULL DEFAULT '{}',
        default_unit TEXT NOT NULL,
        category TEXT NOT NULL,
        sort_order INTEGER NOT NULL,
        value_kind TEXT NOT NULL CHECK (value_kind IN ('circumference', 'weight')),
        source_payload JSONB NOT NULL,
        loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ops.ingestion_run_measurement_files (
        run_id UUID NOT NULL REFERENCES ops.ingestion_runs (run_id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        measurement_session_id TEXT NOT NULL,
        subject_profile_id TEXT NOT NULL,
        source_quality TEXT NOT NULL,
        file_sha256 TEXT NOT NULL,
        loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (run_id, file_path)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_measurement_sessions_date
    ON raw.body_measurement_sessions (measured_date DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_measurement_sessions_subject_date
    ON raw.body_measurement_sessions (subject_profile_id, measured_date DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_measurement_values_session
    ON raw.body_measurement_values (measurement_session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_measurement_values_canonical
    ON raw.body_measurement_values (measurement_type_canonical)
    """,
)


def ensure_stage_1_2_schema(postgres_dsn: str) -> None:
    with connect(postgres_dsn) as connection:
        with connection.cursor() as cursor:
            for statement in POSTGRES_STAGE_1_2_DDL:
                cursor.execute(statement)
        connection.commit()


def start_run(postgres_dsn: str, run_id: UUID, source_file_count: int, details: dict[str, Any]) -> None:
    with connect(postgres_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ops.ingestion_runs (run_id, status, source_file_count, details)
                VALUES (%(run_id)s, 'running', %(source_file_count)s, %(details)s)
                """,
                {
                    "run_id": run_id,
                    "source_file_count": source_file_count,
                    "details": Jsonb(details),
                },
            )
        connection.commit()


def finish_run(postgres_dsn: str, run_id: UUID, status: str, details: dict[str, Any]) -> None:
    with connect(postgres_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ops.ingestion_runs
                SET status = %(status)s,
                    finished_at = NOW(),
                    details = details || %(details)s
                WHERE run_id = %(run_id)s
                """,
                {
                    "run_id": run_id,
                    "status": status,
                    "details": Jsonb(details),
                },
            )
        connection.commit()


def load_dataset(postgres_dsn: str, run_id: UUID, dataset: FlattenedData) -> dict[str, int]:
    return load_workout_dataset(postgres_dsn=postgres_dsn, run_id=run_id, dataset=dataset)


def load_workout_dataset(postgres_dsn: str, run_id: UUID, dataset: FlattenedData) -> dict[str, int]:
    with connect(postgres_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    raw.sets,
                    raw.cardio_segments,
                    raw.recovery_events,
                    raw.exercise_instances,
                    raw.workouts,
                    raw.exercise_dictionary
                CASCADE
                """
            )

            cursor.executemany(
                """
                INSERT INTO raw.workouts (
                    workout_id,
                    workout_date,
                    session_sequence,
                    title_raw,
                    split_raw,
                    split_normalized,
                    source_type,
                    source_quality,
                    source_text,
                    notes,
                    raw_payload
                ) VALUES (
                    %(workout_id)s,
                    %(workout_date)s,
                    %(session_sequence)s,
                    %(title_raw)s,
                    %(split_raw)s,
                    %(split_normalized)s,
                    %(source_type)s,
                    %(source_quality)s,
                    %(source_text)s,
                    %(notes)s,
                    %(raw_payload)s
                )
                """,
                [{**row, "raw_payload": Jsonb(row["raw_payload"])} for row in dataset.workouts],
            )

            cursor.executemany(
                """
                INSERT INTO raw.exercise_instances (
                    exercise_instance_id,
                    workout_id,
                    exercise_order,
                    exercise_name_raw,
                    exercise_name_canonical,
                    category,
                    load_type,
                    bodyweight,
                    attributes,
                    raw_sets_text,
                    notes,
                    source_quality,
                    raw_payload
                ) VALUES (
                    %(exercise_instance_id)s,
                    %(workout_id)s,
                    %(exercise_order)s,
                    %(exercise_name_raw)s,
                    %(exercise_name_canonical)s,
                    %(category)s,
                    %(load_type)s,
                    %(bodyweight)s,
                    %(attributes)s,
                    %(raw_sets_text)s,
                    %(notes)s,
                    %(source_quality)s,
                    %(raw_payload)s
                )
                """,
                [
                    {
                        **row,
                        "attributes": Jsonb(row["attributes"]),
                        "raw_payload": Jsonb(row["raw_payload"]),
                    }
                    for row in dataset.exercise_instances
                ],
            )

            cursor.executemany(
                """
                INSERT INTO raw.sets (
                    exercise_instance_id,
                    workout_id,
                    set_order,
                    weight_kg,
                    reps,
                    raw_value,
                    parse_note,
                    raw_payload
                ) VALUES (
                    %(exercise_instance_id)s,
                    %(workout_id)s,
                    %(set_order)s,
                    %(weight_kg)s,
                    %(reps)s,
                    %(raw_value)s,
                    %(parse_note)s,
                    %(raw_payload)s
                )
                """,
                [{**row, "raw_payload": Jsonb(row["raw_payload"])} for row in dataset.sets],
            )

            cursor.executemany(
                """
                INSERT INTO raw.cardio_segments (
                    workout_id,
                    segment_order,
                    machine,
                    direction,
                    duration_min,
                    notes,
                    raw_payload
                ) VALUES (
                    %(workout_id)s,
                    %(segment_order)s,
                    %(machine)s,
                    %(direction)s,
                    %(duration_min)s,
                    %(notes)s,
                    %(raw_payload)s
                )
                """,
                [{**row, "raw_payload": Jsonb(row["raw_payload"])} for row in dataset.cardio_segments],
            )

            cursor.executemany(
                """
                INSERT INTO raw.recovery_events (
                    workout_id,
                    event_order,
                    event_type,
                    duration_min,
                    notes,
                    raw_payload
                ) VALUES (
                    %(workout_id)s,
                    %(event_order)s,
                    %(event_type)s,
                    %(duration_min)s,
                    %(notes)s,
                    %(raw_payload)s
                )
                """,
                [{**row, "raw_payload": Jsonb(row["raw_payload"])} for row in dataset.recovery_events],
            )

            cursor.executemany(
                """
                INSERT INTO raw.exercise_dictionary (
                    exercise_name_canonical,
                    aliases,
                    category,
                    load_type,
                    bodyweight_default,
                    primary_muscles,
                    source_payload
                ) VALUES (
                    %(exercise_name_canonical)s,
                    %(aliases)s,
                    %(category)s,
                    %(load_type)s,
                    %(bodyweight_default)s,
                    %(primary_muscles)s,
                    %(source_payload)s
                )
                """,
                [
                    {
                        **row,
                        "source_payload": Jsonb(row["source_payload"]),
                    }
                    for row in dataset.exercise_dictionary
                ],
            )

            cursor.executemany(
                """
                INSERT INTO ops.ingestion_run_files (
                    run_id,
                    file_path,
                    workout_id,
                    source_quality,
                    file_sha256
                ) VALUES (
                    %(run_id)s,
                    %(file_path)s,
                    %(workout_id)s,
                    %(source_quality)s,
                    %(file_sha256)s
                )
                """,
                [{"run_id": run_id, **row} for row in dataset.source_files],
            )

        connection.commit()

    return {
        "workouts": len(dataset.workouts),
        "exercise_instances": len(dataset.exercise_instances),
        "sets": len(dataset.sets),
        "cardio_segments": len(dataset.cardio_segments),
        "recovery_events": len(dataset.recovery_events),
        "exercise_dictionary": len(dataset.exercise_dictionary),
        "source_files": len(dataset.source_files),
    }


def load_measurement_dataset(
    postgres_dsn: str,
    run_id: UUID,
    dataset: MeasurementFlattenedData,
) -> dict[str, int]:
    with connect(postgres_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    raw.body_measurement_values,
                    raw.body_measurement_sessions,
                    raw.measurement_type_dictionary,
                    raw.subject_profiles
                CASCADE
                """
            )

            cursor.executemany(
                """
                INSERT INTO raw.subject_profiles (
                    subject_profile_id,
                    profile_kind,
                    display_name,
                    is_default,
                    notes,
                    source_payload
                ) VALUES (
                    %(subject_profile_id)s,
                    %(profile_kind)s,
                    %(display_name)s,
                    %(is_default)s,
                    %(notes)s,
                    %(source_payload)s
                )
                """,
                [
                    {**row, "source_payload": Jsonb(row["source_payload"])}
                    for row in dataset.subject_profiles
                ],
            )

            cursor.executemany(
                """
                INSERT INTO raw.measurement_type_dictionary (
                    measurement_type_canonical,
                    aliases,
                    default_unit,
                    category,
                    sort_order,
                    value_kind,
                    source_payload
                ) VALUES (
                    %(measurement_type_canonical)s,
                    %(aliases)s,
                    %(default_unit)s,
                    %(category)s,
                    %(sort_order)s,
                    %(value_kind)s,
                    %(source_payload)s
                )
                """,
                [
                    {**row, "source_payload": Jsonb(row["source_payload"])}
                    for row in dataset.measurement_type_dictionary
                ],
            )

            cursor.executemany(
                """
                INSERT INTO raw.body_measurement_sessions (
                    measurement_session_id,
                    subject_profile_id,
                    measured_at,
                    measured_date,
                    source_type,
                    source_quality,
                    context_time_of_day,
                    fasting_state,
                    before_training,
                    notes,
                    raw_payload
                ) VALUES (
                    %(measurement_session_id)s,
                    %(subject_profile_id)s,
                    %(measured_at)s,
                    %(measured_date)s,
                    %(source_type)s,
                    %(source_quality)s,
                    %(context_time_of_day)s,
                    %(fasting_state)s,
                    %(before_training)s,
                    %(notes)s,
                    %(raw_payload)s
                )
                """,
                [
                    {**row, "raw_payload": Jsonb(row["raw_payload"])}
                    for row in dataset.body_measurement_sessions
                ],
            )

            cursor.executemany(
                """
                INSERT INTO raw.body_measurement_values (
                    measurement_value_id,
                    measurement_session_id,
                    measurement_type_canonical,
                    measurement_type_raw,
                    value_numeric,
                    unit,
                    side_or_scope,
                    raw_value,
                    parse_note,
                    notes,
                    order_in_session,
                    raw_payload
                ) VALUES (
                    %(measurement_value_id)s,
                    %(measurement_session_id)s,
                    %(measurement_type_canonical)s,
                    %(measurement_type_raw)s,
                    %(value_numeric)s,
                    %(unit)s,
                    %(side_or_scope)s,
                    %(raw_value)s,
                    %(parse_note)s,
                    %(notes)s,
                    %(order_in_session)s,
                    %(raw_payload)s
                )
                """,
                [
                    {**row, "raw_payload": Jsonb(row["raw_payload"])}
                    for row in dataset.body_measurement_values
                ],
            )

            cursor.executemany(
                """
                INSERT INTO ops.ingestion_run_measurement_files (
                    run_id,
                    file_path,
                    measurement_session_id,
                    subject_profile_id,
                    source_quality,
                    file_sha256
                ) VALUES (
                    %(run_id)s,
                    %(file_path)s,
                    %(measurement_session_id)s,
                    %(subject_profile_id)s,
                    %(source_quality)s,
                    %(file_sha256)s
                )
                """,
                [{"run_id": run_id, **row} for row in dataset.source_files],
            )

        connection.commit()

    return {
        "subject_profiles": len(dataset.subject_profiles),
        "body_measurement_sessions": len(dataset.body_measurement_sessions),
        "body_measurement_values": len(dataset.body_measurement_values),
        "measurement_type_dictionary": len(dataset.measurement_type_dictionary),
        "source_files": len(dataset.source_files),
    }
