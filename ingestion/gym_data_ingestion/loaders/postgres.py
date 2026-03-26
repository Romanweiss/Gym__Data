from typing import Any
from uuid import UUID

from psycopg import connect
from psycopg.types.json import Jsonb

from gym_data_ingestion.models import FlattenedData


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
