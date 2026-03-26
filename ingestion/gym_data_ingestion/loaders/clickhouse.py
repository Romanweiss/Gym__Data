from collections import defaultdict
from datetime import timedelta
from typing import Any

import clickhouse_connect

from gym_data_ingestion.models import FlattenedData

V2_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS {database}.mart_workout_detail_rollup
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
    ORDER BY (workout_date, workout_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS {database}.mart_exercise_progress
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
    ORDER BY (exercise_name_canonical, workout_date, workout_id, display_order)
    """,
    """
    CREATE TABLE IF NOT EXISTS {database}.mart_weekly_training_load
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
    ORDER BY week_start
    """,
    """
    CREATE TABLE IF NOT EXISTS {database}.mart_cardio_summary
    (
        week_start Date,
        machine String,
        direction String,
        workouts_total UInt32,
        segments_total UInt32,
        cardio_minutes UInt32
    )
    ENGINE = MergeTree
    ORDER BY (week_start, machine, direction)
    """,
    """
    CREATE TABLE IF NOT EXISTS {database}.mart_recovery_summary
    (
        week_start Date,
        event_type String,
        workouts_total UInt32,
        recovery_events_total UInt32,
        recovery_minutes UInt32
    )
    ENGINE = MergeTree
    ORDER BY (week_start, event_type)
    """,
    """
    CREATE VIEW IF NOT EXISTS {database}.v_exercise_progress_rollup AS
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
    FROM {database}.mart_exercise_progress AS progress
    GROUP BY progress.exercise_name_canonical
    """,
)

TRUNCATE_TABLES = (
    "mart_workout_summary",
    "mart_exercise_daily",
    "mart_workout_detail_rollup",
    "mart_exercise_progress",
    "mart_weekly_training_load",
    "mart_cardio_summary",
    "mart_recovery_summary",
)


def load_marts(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    dataset: FlattenedData,
) -> dict[str, int]:
    payloads = _build_mart_payloads(dataset)

    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
    )
    try:
        _ensure_v2_schema(client, database)
        for table_name in TRUNCATE_TABLES:
            client.command(f"TRUNCATE TABLE {database}.{table_name}")

        for table_name, payload in payloads.items():
            if payload["rows"]:
                client.insert(
                    f"{database}.{table_name}",
                    payload["rows"],
                    column_names=payload["columns"],
                )
    finally:
        client.close()

    return {table_name: len(payload["rows"]) for table_name, payload in payloads.items()}


def _build_mart_payloads(dataset: FlattenedData) -> dict[str, dict[str, Any]]:
    sets_by_exercise: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exercises_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cardio_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recovery_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dictionary_by_canonical = {
        row["exercise_name_canonical"]: row for row in dataset.exercise_dictionary
    }

    for set_row in dataset.sets:
        sets_by_exercise[set_row["exercise_instance_id"]].append(set_row)

    for exercise_row in dataset.exercise_instances:
        exercises_by_workout[exercise_row["workout_id"]].append(exercise_row)

    for cardio_row in dataset.cardio_segments:
        cardio_by_workout[cardio_row["workout_id"]].append(cardio_row)

    for recovery_row in dataset.recovery_events:
        recovery_by_workout[recovery_row["workout_id"]].append(recovery_row)

    workout_summary_rows: list[list[Any]] = []
    exercise_daily_rows: list[list[Any]] = []
    workout_detail_rows: list[list[Any]] = []
    exercise_progress_rows: list[list[Any]] = []
    weekly_training_load_rows: list[list[Any]] = []
    cardio_summary_rows: list[list[Any]] = []
    recovery_summary_rows: list[list[Any]] = []

    weekly_rollups: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {
            "workouts_total": 0,
            "raw_detailed_workouts": 0,
            "partial_raw_workouts": 0,
            "summary_only_workouts": 0,
            "exercise_instances_total": 0,
            "set_count": 0,
            "total_reps": 0,
            "total_volume_kg": 0.0,
            "cardio_minutes": 0,
            "recovery_events_total": 0,
            "recovery_minutes": 0,
        }
    )
    cardio_rollups: dict[tuple[Any, str, str], dict[str, Any]] = defaultdict(
        lambda: {"workout_ids": set(), "segments_total": 0, "cardio_minutes": 0}
    )
    recovery_rollups: dict[tuple[Any, str], dict[str, Any]] = defaultdict(
        lambda: {"workout_ids": set(), "recovery_events_total": 0, "recovery_minutes": 0}
    )

    for workout in sorted(dataset.workouts, key=lambda row: (row["workout_date"], row["workout_id"])):
        workout_id = workout["workout_id"]
        week_start = _week_start(workout["workout_date"])
        exercise_instances = sorted(
            exercises_by_workout[workout_id],
            key=lambda row: _display_order(row["exercise_instance_id"]),
        )
        cardio_segments = sorted(
            cardio_by_workout[workout_id],
            key=lambda row: int(row["segment_order"]),
        )
        recovery_events = sorted(
            recovery_by_workout[workout_id],
            key=lambda row: int(row["event_order"]),
        )

        set_count = 0
        total_reps = 0
        total_volume_kg = 0.0
        tracked_exercise_count = 0
        distinct_canonical_exercise_count = len(
            {row["exercise_name_canonical"] for row in exercise_instances}
        )
        bodyweight_exercise_count = 0
        bodyweight_set_count = 0

        for exercise in exercise_instances:
            exercise_sets = sorted(
                sets_by_exercise[exercise["exercise_instance_id"]],
                key=lambda row: int(row["set_order"]),
            )
            exercise_reps = sum(int(set_row["reps"]) for set_row in exercise_sets)
            exercise_volume = float(
                sum(float(set_row["weight_kg"]) * int(set_row["reps"]) for set_row in exercise_sets)
            )
            max_weight_kg = max((float(set_row["weight_kg"]) for set_row in exercise_sets), default=0.0)
            max_reps_in_set = max((int(set_row["reps"]) for set_row in exercise_sets), default=0)

            if exercise_sets:
                tracked_exercise_count += 1
            if exercise["bodyweight"]:
                bodyweight_exercise_count += 1
                bodyweight_set_count += len(exercise_sets)

            set_count += len(exercise_sets)
            total_reps += exercise_reps
            total_volume_kg += exercise_volume

            dictionary_row = dictionary_by_canonical.get(exercise["exercise_name_canonical"], {})
            primary_muscles = list(dictionary_row.get("primary_muscles", []))

            exercise_daily_rows.append(
                [
                    workout["workout_date"],
                    workout_id,
                    int(workout["session_sequence"]),
                    exercise["exercise_name_canonical"],
                    exercise["category"],
                    exercise["load_type"],
                    exercise["source_quality"],
                    1 if exercise["bodyweight"] else 0,
                    1,
                    1 if exercise_sets else 0,
                    len(exercise_sets),
                    exercise_reps,
                    exercise_volume,
                    max_weight_kg,
                ]
            )

            exercise_progress_rows.append(
                [
                    workout["workout_date"],
                    workout_id,
                    int(workout["session_sequence"]),
                    exercise["exercise_instance_id"],
                    _display_order(exercise["exercise_instance_id"]),
                    float(exercise["exercise_order"]),
                    exercise["exercise_name_canonical"],
                    exercise["exercise_name_raw"],
                    exercise["category"],
                    exercise["load_type"],
                    exercise["source_quality"],
                    1 if exercise["bodyweight"] else 0,
                    list(workout["split_normalized"]),
                    primary_muscles,
                    len(exercise_sets),
                    exercise_reps,
                    exercise_volume,
                    max_weight_kg,
                    max_reps_in_set,
                ]
            )

        cardio_minutes = sum(int(row["duration_min"] or 0) for row in cardio_segments)
        recovery_minutes = sum(int(row["duration_min"] or 0) for row in recovery_events)

        workout_summary_rows.append(
            [
                workout_id,
                workout["workout_date"],
                int(workout["session_sequence"]),
                workout["source_quality"],
                workout["title_raw"],
                list(workout["split_normalized"]),
                len(exercise_instances),
                tracked_exercise_count,
                set_count,
                total_reps,
                float(total_volume_kg),
                cardio_minutes,
                recovery_minutes,
                1 if set_count > 0 else 0,
            ]
        )

        workout_detail_rows.append(
            [
                workout_id,
                workout["workout_date"],
                int(workout["session_sequence"]),
                workout["source_quality"],
                workout["title_raw"],
                list(workout["split_normalized"]),
                len(exercise_instances),
                tracked_exercise_count,
                distinct_canonical_exercise_count,
                bodyweight_exercise_count,
                bodyweight_set_count,
                set_count,
                total_reps,
                float(total_volume_kg),
                len(cardio_segments),
                cardio_minutes,
                len(recovery_events),
                recovery_minutes,
            ]
        )

        weekly_rollup = weekly_rollups[week_start]
        weekly_rollup["workouts_total"] += 1
        weekly_rollup[f"{workout['source_quality']}_workouts"] += 1
        weekly_rollup["exercise_instances_total"] += len(exercise_instances)
        weekly_rollup["set_count"] += set_count
        weekly_rollup["total_reps"] += total_reps
        weekly_rollup["total_volume_kg"] += float(total_volume_kg)
        weekly_rollup["cardio_minutes"] += cardio_minutes
        weekly_rollup["recovery_events_total"] += len(recovery_events)
        weekly_rollup["recovery_minutes"] += recovery_minutes

        for cardio_row in cardio_segments:
            key = (
                week_start,
                str(cardio_row["machine"]),
                str(cardio_row.get("direction") or ""),
            )
            bucket = cardio_rollups[key]
            bucket["workout_ids"].add(workout_id)
            bucket["segments_total"] += 1
            bucket["cardio_minutes"] += int(cardio_row["duration_min"] or 0)

        for recovery_row in recovery_events:
            key = (week_start, str(recovery_row["event_type"]))
            bucket = recovery_rollups[key]
            bucket["workout_ids"].add(workout_id)
            bucket["recovery_events_total"] += 1
            bucket["recovery_minutes"] += int(recovery_row["duration_min"] or 0)

    for week_start in sorted(weekly_rollups):
        row = weekly_rollups[week_start]
        weekly_training_load_rows.append(
            [
                week_start,
                row["workouts_total"],
                row["raw_detailed_workouts"],
                row["partial_raw_workouts"],
                row["summary_only_workouts"],
                row["exercise_instances_total"],
                row["set_count"],
                row["total_reps"],
                float(row["total_volume_kg"]),
                row["cardio_minutes"],
                row["recovery_events_total"],
                row["recovery_minutes"],
            ]
        )

    for key in sorted(cardio_rollups):
        week_start, machine, direction = key
        row = cardio_rollups[key]
        cardio_summary_rows.append(
            [
                week_start,
                machine,
                direction,
                len(row["workout_ids"]),
                row["segments_total"],
                row["cardio_minutes"],
            ]
        )

    for key in sorted(recovery_rollups):
        week_start, event_type = key
        row = recovery_rollups[key]
        recovery_summary_rows.append(
            [
                week_start,
                event_type,
                len(row["workout_ids"]),
                row["recovery_events_total"],
                row["recovery_minutes"],
            ]
        )

    return {
        "mart_workout_summary": {
            "columns": [
                "workout_id",
                "workout_date",
                "session_sequence",
                "source_quality",
                "title_raw",
                "split_normalized",
                "exercise_count",
                "set_tracked_exercise_count",
                "set_count",
                "total_reps",
                "total_volume_kg",
                "cardio_minutes",
                "recovery_minutes",
                "has_set_level_data",
            ],
            "rows": workout_summary_rows,
        },
        "mart_exercise_daily": {
            "columns": [
                "workout_date",
                "workout_id",
                "session_sequence",
                "exercise_name_canonical",
                "category",
                "load_type",
                "source_quality",
                "bodyweight",
                "workout_appearance",
                "has_set_level_data",
                "set_count",
                "total_reps",
                "total_volume_kg",
                "max_weight_kg",
            ],
            "rows": exercise_daily_rows,
        },
        "mart_workout_detail_rollup": {
            "columns": [
                "workout_id",
                "workout_date",
                "session_sequence",
                "source_quality",
                "title_raw",
                "split_normalized",
                "exercise_count",
                "tracked_exercise_count",
                "distinct_canonical_exercise_count",
                "bodyweight_exercise_count",
                "bodyweight_set_count",
                "set_count",
                "total_reps",
                "total_volume_kg",
                "cardio_segments_count",
                "cardio_minutes",
                "recovery_events_count",
                "recovery_minutes",
            ],
            "rows": workout_detail_rows,
        },
        "mart_exercise_progress": {
            "columns": [
                "workout_date",
                "workout_id",
                "session_sequence",
                "exercise_instance_id",
                "display_order",
                "exercise_order",
                "exercise_name_canonical",
                "exercise_name_raw",
                "category",
                "load_type",
                "source_quality",
                "bodyweight",
                "split_normalized",
                "primary_muscles",
                "set_count",
                "total_reps",
                "total_volume_kg",
                "max_weight_kg",
                "max_reps_in_set",
            ],
            "rows": exercise_progress_rows,
        },
        "mart_weekly_training_load": {
            "columns": [
                "week_start",
                "workouts_total",
                "raw_detailed_workouts",
                "partial_raw_workouts",
                "summary_only_workouts",
                "exercise_instances_total",
                "set_count",
                "total_reps",
                "total_volume_kg",
                "cardio_minutes",
                "recovery_events_total",
                "recovery_minutes",
            ],
            "rows": weekly_training_load_rows,
        },
        "mart_cardio_summary": {
            "columns": [
                "week_start",
                "machine",
                "direction",
                "workouts_total",
                "segments_total",
                "cardio_minutes",
            ],
            "rows": cardio_summary_rows,
        },
        "mart_recovery_summary": {
            "columns": [
                "week_start",
                "event_type",
                "workouts_total",
                "recovery_events_total",
                "recovery_minutes",
            ],
            "rows": recovery_summary_rows,
        },
    }


def _ensure_v2_schema(client: Any, database: str) -> None:
    for statement in V2_SCHEMA_STATEMENTS:
        client.command(statement.format(database=database))


def _week_start(workout_date: Any):
    return workout_date - timedelta(days=workout_date.weekday())


def _display_order(exercise_instance_id: str) -> int:
    return int(str(exercise_instance_id).rsplit("_ex_", 1)[1])
