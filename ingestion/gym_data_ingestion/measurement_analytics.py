from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from gym_data_ingestion.measurement_models import MeasurementFlattenedData
from gym_data_ingestion.models import FlattenedData


def build_measurement_mart_payloads(
    workout_dataset: FlattenedData,
    measurement_dataset: MeasurementFlattenedData,
    cadence_days: int,
    default_subject_profile_id: str,
    as_of_date: date | None = None,
) -> dict[str, dict[str, Any]]:
    reference_date = as_of_date or date.today()
    session_by_id = {
        row["measurement_session_id"]: row for row in measurement_dataset.body_measurement_sessions
    }
    measurement_type_by_canonical = {
        row["measurement_type_canonical"]: row
        for row in measurement_dataset.measurement_type_dictionary
    }
    values_by_subject_and_type: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    sessions_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)

    workout_rows = sorted(
        workout_dataset.workouts,
        key=lambda row: (row["workout_date"], row["workout_id"]),
    )
    workout_metrics_by_id = _build_workout_metrics(workout_dataset)

    for session in measurement_dataset.body_measurement_sessions:
        sessions_by_subject[session["subject_profile_id"]].append(session)

    for value in measurement_dataset.body_measurement_values:
        session = session_by_id[value["measurement_session_id"]]
        values_by_subject_and_type[
            (session["subject_profile_id"], value["measurement_type_canonical"])
        ].append({**value, "_session": session})

    progress_rows: list[list[Any]] = []
    delta_rows: list[list[Any]] = []
    latest_rows: list[list[Any]] = []
    overdue_rows: list[list[Any]] = []
    vs_workout_activity_rows: list[list[Any]] = []

    for subject_profile_id, sessions in sessions_by_subject.items():
        ordered_sessions = sorted(
            sessions,
            key=lambda row: (row["measured_at"], row["measurement_session_id"]),
        )
        sessions_by_subject[subject_profile_id] = ordered_sessions

        previous_session = None
        for session in ordered_sessions:
            activity = _session_activity_bridge(
                workout_rows=workout_rows,
                workout_metrics_by_id=workout_metrics_by_id,
                previous_session=previous_session,
                current_session=session,
                default_subject_profile_id=default_subject_profile_id,
                current_subject_profile_id=subject_profile_id,
            )
            vs_workout_activity_rows.append(
                [
                    subject_profile_id,
                    session["measurement_session_id"],
                    session["measured_date"],
                    previous_session["measurement_session_id"] if previous_session else None,
                    previous_session["measured_date"] if previous_session else None,
                    activity["workouts_since_previous_measurement"],
                    activity["total_sets_since_previous_measurement"],
                    activity["total_reps_since_previous_measurement"],
                    activity["total_volume_kg_since_previous_measurement"],
                    activity["cardio_minutes_since_previous_measurement"],
                    activity["recovery_minutes_since_previous_measurement"],
                    activity["last_workout_before_measurement_id"],
                    activity["last_workout_before_measurement_date"],
                ]
            )
            previous_session = session

        latest_session = ordered_sessions[-1]
        overdue_activity = _activity_since_last_measurement(
            workout_rows=workout_rows,
            latest_session=latest_session,
            default_subject_profile_id=default_subject_profile_id,
            current_subject_profile_id=subject_profile_id,
        )
        days_since_last_measurement = max(
            0,
            (reference_date - latest_session["measured_date"]).days,
        )
        recommended_now = days_since_last_measurement >= cadence_days
        recommendation_reason = (
            f"No measurement for {days_since_last_measurement} days; cadence threshold is {cadence_days} days."
            if recommended_now
            else f"Last measurement is within the configured {cadence_days}-day cadence."
        )
        overdue_rows.append(
            [
                subject_profile_id,
                cadence_days,
                latest_session["measurement_session_id"],
                latest_session["measured_at"],
                latest_session["measured_date"],
                days_since_last_measurement,
                overdue_activity["workouts_since_last_measurement"],
                overdue_activity["last_workout_date"],
                1 if recommended_now else 0,
                recommendation_reason,
            ]
        )

    for key, values in values_by_subject_and_type.items():
        subject_profile_id, measurement_type_canonical = key
        ordered_values = sorted(
            values,
            key=lambda row: (row["_session"]["measured_at"], row["order_in_session"]),
        )
        dictionary_row = measurement_type_by_canonical[measurement_type_canonical]

        previous_value = None
        for value in ordered_values:
            session = value["_session"]
            activity = _session_activity_bridge(
                workout_rows=workout_rows,
                workout_metrics_by_id=workout_metrics_by_id,
                previous_session=previous_value["_session"] if previous_value else None,
                current_session=session,
                default_subject_profile_id=default_subject_profile_id,
                current_subject_profile_id=subject_profile_id,
            )
            previous_session_id = None
            previous_measured_date = None
            previous_value_numeric = None
            delta_value_numeric = None
            days_since_previous = None

            if previous_value is not None:
                previous_session_id = previous_value["measurement_session_id"]
                previous_measured_date = previous_value["_session"]["measured_date"]
                previous_value_numeric = float(previous_value["value_numeric"])
                delta_value_numeric = round(
                    float(value["value_numeric"]) - previous_value_numeric,
                    2,
                )
                days_since_previous = (
                    session["measured_date"] - previous_value["_session"]["measured_date"]
                ).days

            progress_rows.append(
                [
                    subject_profile_id,
                    value["measurement_session_id"],
                    session["measured_at"],
                    session["measured_date"],
                    measurement_type_canonical,
                    value["measurement_type_raw"],
                    dictionary_row["category"],
                    dictionary_row["value_kind"],
                    int(dictionary_row["sort_order"]),
                    value["unit"],
                    value["side_or_scope"],
                    session["source_quality"],
                    session["context_time_of_day"],
                    float(value["value_numeric"]),
                    previous_session_id,
                    previous_measured_date,
                    previous_value_numeric,
                    delta_value_numeric,
                    days_since_previous,
                    activity["workouts_since_previous_measurement"],
                    activity["total_sets_since_previous_measurement"],
                    activity["total_reps_since_previous_measurement"],
                    activity["total_volume_kg_since_previous_measurement"],
                    activity["cardio_minutes_since_previous_measurement"],
                    activity["recovery_minutes_since_previous_measurement"],
                ]
            )

            delta_rows.append(
                [
                    subject_profile_id,
                    value["measurement_session_id"],
                    session["measured_date"],
                    measurement_type_canonical,
                    value["unit"],
                    float(value["value_numeric"]),
                    previous_session_id,
                    previous_measured_date,
                    previous_value_numeric,
                    delta_value_numeric,
                    days_since_previous,
                ]
            )
            previous_value = value

        latest_value = ordered_values[-1]
        previous_value = ordered_values[-2] if len(ordered_values) > 1 else None
        previous_measured_date = (
            previous_value["_session"]["measured_date"] if previous_value else None
        )
        previous_value_numeric = (
            float(previous_value["value_numeric"]) if previous_value else None
        )
        delta_value_numeric = (
            round(float(latest_value["value_numeric"]) - previous_value_numeric, 2)
            if previous_value is not None
            else None
        )
        days_since_previous = (
            (
                latest_value["_session"]["measured_date"]
                - previous_value["_session"]["measured_date"]
            ).days
            if previous_value is not None
            else None
        )
        latest_rows.append(
            [
                subject_profile_id,
                measurement_type_canonical,
                dictionary_row["category"],
                dictionary_row["value_kind"],
                int(dictionary_row["sort_order"]),
                latest_value["unit"],
                latest_value["measurement_session_id"],
                latest_value["_session"]["measured_at"],
                latest_value["_session"]["measured_date"],
                float(latest_value["value_numeric"]),
                previous_value["measurement_session_id"] if previous_value else None,
                previous_measured_date,
                previous_value_numeric,
                delta_value_numeric,
                days_since_previous,
            ]
        )

    return {
        "mart_measurement_progress": {
            "columns": [
                "subject_profile_id",
                "measurement_session_id",
                "measured_at",
                "measured_date",
                "measurement_type_canonical",
                "measurement_type_raw",
                "category",
                "value_kind",
                "sort_order",
                "unit",
                "side_or_scope",
                "source_quality",
                "context_time_of_day",
                "value_numeric",
                "previous_measurement_session_id",
                "previous_measured_date",
                "previous_value_numeric",
                "delta_value_numeric",
                "days_since_previous",
                "workouts_since_previous_measurement",
                "total_sets_since_previous_measurement",
                "total_reps_since_previous_measurement",
                "total_volume_kg_since_previous_measurement",
                "cardio_minutes_since_previous_measurement",
                "recovery_minutes_since_previous_measurement",
            ],
            "rows": progress_rows,
        },
        "mart_measurement_deltas": {
            "columns": [
                "subject_profile_id",
                "measurement_session_id",
                "measured_date",
                "measurement_type_canonical",
                "unit",
                "value_numeric",
                "previous_measurement_session_id",
                "previous_measured_date",
                "previous_value_numeric",
                "delta_value_numeric",
                "days_since_previous",
            ],
            "rows": delta_rows,
        },
        "mart_measurement_latest": {
            "columns": [
                "subject_profile_id",
                "measurement_type_canonical",
                "category",
                "value_kind",
                "sort_order",
                "unit",
                "latest_measurement_session_id",
                "latest_measured_at",
                "latest_measured_date",
                "latest_value_numeric",
                "previous_measurement_session_id",
                "previous_measured_date",
                "previous_value_numeric",
                "delta_value_numeric",
                "days_since_previous",
            ],
            "rows": latest_rows,
        },
        "mart_measurement_overdue": {
            "columns": [
                "subject_profile_id",
                "cadence_days",
                "last_measurement_session_id",
                "last_measured_at",
                "last_measured_date",
                "days_since_last_measurement",
                "workouts_since_last_measurement",
                "last_workout_date",
                "recommended_now",
                "recommendation_reason",
            ],
            "rows": overdue_rows,
        },
        "mart_measurement_vs_workout_activity": {
            "columns": [
                "subject_profile_id",
                "measurement_session_id",
                "measured_date",
                "previous_measurement_session_id",
                "previous_measured_date",
                "workouts_since_previous_measurement",
                "total_sets_since_previous_measurement",
                "total_reps_since_previous_measurement",
                "total_volume_kg_since_previous_measurement",
                "cardio_minutes_since_previous_measurement",
                "recovery_minutes_since_previous_measurement",
                "last_workout_before_measurement_id",
                "last_workout_before_measurement_date",
            ],
            "rows": vs_workout_activity_rows,
        },
    }


def _build_workout_metrics(dataset: FlattenedData) -> dict[str, dict[str, Any]]:
    sets_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cardio_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recovery_by_workout: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for set_row in dataset.sets:
        sets_by_workout[set_row["workout_id"]].append(set_row)
    for cardio_row in dataset.cardio_segments:
        cardio_by_workout[cardio_row["workout_id"]].append(cardio_row)
    for recovery_row in dataset.recovery_events:
        recovery_by_workout[recovery_row["workout_id"]].append(recovery_row)

    metrics_by_id: dict[str, dict[str, Any]] = {}
    for workout in dataset.workouts:
        workout_id = workout["workout_id"]
        workout_sets = sets_by_workout[workout_id]
        metrics_by_id[workout_id] = {
            "workout_id": workout_id,
            "workout_date": workout["workout_date"],
            "set_count": len(workout_sets),
            "total_reps": sum(int(row["reps"]) for row in workout_sets),
            "total_volume_kg": float(
                sum(float(row["weight_kg"]) * int(row["reps"]) for row in workout_sets)
            ),
            "cardio_minutes": sum(
                int(row["duration_min"] or 0) for row in cardio_by_workout[workout_id]
            ),
            "recovery_minutes": sum(
                int(row["duration_min"] or 0) for row in recovery_by_workout[workout_id]
            ),
        }
    return metrics_by_id


def _session_activity_bridge(
    workout_rows: list[dict[str, Any]],
    workout_metrics_by_id: dict[str, dict[str, Any]],
    previous_session: dict[str, Any] | None,
    current_session: dict[str, Any],
    default_subject_profile_id: str,
    current_subject_profile_id: str,
) -> dict[str, Any]:
    workouts_in_window = _workouts_between_sessions(
        workout_rows=workout_rows,
        previous_session=previous_session,
        current_session=current_session,
        default_subject_profile_id=default_subject_profile_id,
        current_subject_profile_id=current_subject_profile_id,
    )
    return _aggregate_workout_bridge(
        workouts_in_window=workouts_in_window,
        workout_metrics_by_id=workout_metrics_by_id,
    )


def _activity_since_last_measurement(
    workout_rows: list[dict[str, Any]],
    latest_session: dict[str, Any],
    default_subject_profile_id: str,
    current_subject_profile_id: str,
) -> dict[str, Any]:
    if current_subject_profile_id != default_subject_profile_id:
        return {
            "workouts_since_last_measurement": 0,
            "last_workout_date": None,
        }

    workouts = [
        row
        for row in workout_rows
        if row["workout_date"] > latest_session["measured_date"]
    ]
    return {
        "workouts_since_last_measurement": len(workouts),
        "last_workout_date": workouts[-1]["workout_date"] if workouts else None,
    }


def _workouts_between_sessions(
    workout_rows: list[dict[str, Any]],
    previous_session: dict[str, Any] | None,
    current_session: dict[str, Any],
    default_subject_profile_id: str,
    current_subject_profile_id: str,
) -> list[dict[str, Any]]:
    if current_subject_profile_id != default_subject_profile_id:
        return []

    current_date = current_session["measured_date"]
    if previous_session is None:
        return [row for row in workout_rows if row["workout_date"] < current_date]

    previous_date = previous_session["measured_date"]
    return [
        row
        for row in workout_rows
        if previous_date < row["workout_date"] < current_date
    ]


def _aggregate_workout_bridge(
    workouts_in_window: list[dict[str, Any]],
    workout_metrics_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    aggregated = {
        "workouts_since_previous_measurement": len(workouts_in_window),
        "total_sets_since_previous_measurement": 0,
        "total_reps_since_previous_measurement": 0,
        "total_volume_kg_since_previous_measurement": 0.0,
        "cardio_minutes_since_previous_measurement": 0,
        "recovery_minutes_since_previous_measurement": 0,
        "last_workout_before_measurement_id": None,
        "last_workout_before_measurement_date": None,
    }

    if workouts_in_window:
        last_workout = workouts_in_window[-1]
        aggregated["last_workout_before_measurement_id"] = last_workout["workout_id"]
        aggregated["last_workout_before_measurement_date"] = last_workout["workout_date"]

    for workout in workouts_in_window:
        metrics = workout_metrics_by_id[workout["workout_id"]]
        aggregated["total_sets_since_previous_measurement"] += int(metrics["set_count"])
        aggregated["total_reps_since_previous_measurement"] += int(metrics["total_reps"])
        aggregated["total_volume_kg_since_previous_measurement"] += float(
            metrics["total_volume_kg"]
        )
        aggregated["cardio_minutes_since_previous_measurement"] += int(
            metrics["cardio_minutes"]
        )
        aggregated["recovery_minutes_since_previous_measurement"] += int(
            metrics["recovery_minutes"]
        )

    aggregated["total_volume_kg_since_previous_measurement"] = round(
        aggregated["total_volume_kg_since_previous_measurement"],
        2,
    )
    return aggregated
