from collections import defaultdict
from typing import Any

import clickhouse_connect

from gym_data_ingestion.models import FlattenedData


def load_marts(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    dataset: FlattenedData,
) -> dict[str, int]:
    workout_rows, exercise_rows = _build_mart_rows(dataset)

    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
    )
    try:
        client.command(f"TRUNCATE TABLE {database}.mart_workout_summary")
        client.command(f"TRUNCATE TABLE {database}.mart_exercise_daily")

        if workout_rows:
            client.insert(
                f"{database}.mart_workout_summary",
                workout_rows,
                column_names=[
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
            )

        if exercise_rows:
            client.insert(
                f"{database}.mart_exercise_daily",
                exercise_rows,
                column_names=[
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
            )
    finally:
        client.close()

    return {
        "mart_workout_summary": len(workout_rows),
        "mart_exercise_daily": len(exercise_rows),
    }


def _build_mart_rows(dataset: FlattenedData) -> tuple[list[list[Any]], list[list[Any]]]:
    sets_by_exercise: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exercises_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cardio_minutes_by_workout: dict[str, int] = defaultdict(int)
    recovery_minutes_by_workout: dict[str, int] = defaultdict(int)

    for set_row in dataset.sets:
        sets_by_exercise[set_row["exercise_instance_id"]].append(set_row)

    for exercise_row in dataset.exercise_instances:
        exercises_by_workout[exercise_row["workout_id"]].append(exercise_row)

    for cardio_row in dataset.cardio_segments:
        cardio_minutes_by_workout[cardio_row["workout_id"]] += int(cardio_row["duration_min"] or 0)

    for recovery_row in dataset.recovery_events:
        recovery_minutes_by_workout[recovery_row["workout_id"]] += int(recovery_row["duration_min"] or 0)

    workout_rows: list[list[Any]] = []
    exercise_rows: list[list[Any]] = []

    for workout in sorted(dataset.workouts, key=lambda row: (row["workout_date"], row["workout_id"])):
        workout_id = workout["workout_id"]
        exercise_instances = exercises_by_workout[workout_id]

        set_count = 0
        total_reps = 0
        total_volume_kg = 0.0
        tracked_exercise_count = 0

        for exercise in exercise_instances:
            exercise_sets = sets_by_exercise[exercise["exercise_instance_id"]]
            exercise_reps = sum(int(set_row["reps"]) for set_row in exercise_sets)
            exercise_volume = float(
                sum(float(set_row["weight_kg"]) * int(set_row["reps"]) for set_row in exercise_sets)
            )
            max_weight_kg = max((float(set_row["weight_kg"]) for set_row in exercise_sets), default=0.0)

            if exercise_sets:
                tracked_exercise_count += 1
            set_count += len(exercise_sets)
            total_reps += exercise_reps
            total_volume_kg += exercise_volume

            exercise_rows.append(
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

        workout_rows.append(
            [
                workout_id,
                workout["workout_date"],
                int(workout["session_sequence"]),
                workout["source_quality"],
                workout["title_raw"],
                workout["split_normalized"],
                len(exercise_instances),
                tracked_exercise_count,
                set_count,
                total_reps,
                float(total_volume_kg),
                cardio_minutes_by_workout[workout_id],
                recovery_minutes_by_workout[workout_id],
                1 if set_count > 0 else 0,
            ]
        )

    return workout_rows, exercise_rows
