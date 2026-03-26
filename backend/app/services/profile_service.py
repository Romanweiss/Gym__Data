from __future__ import annotations

from datetime import date, datetime, time

from app.core.config import get_settings
from app.db.postgres import get_postgres_client
from app.services.analytics_service import (
    get_cardio_analytics,
    get_recovery_analytics,
    get_weekly_training_load,
)
from app.services.measurement_service import (
    get_latest_measurements,
    get_measurement_overdue,
    list_measurement_sessions,
)
from app.services.serialization import normalize_records
from app.services.workout_service import get_workout_summary, list_workouts

TIMELINE_MEASUREMENTS_QUERY = """
SELECT
    s.measurement_session_id,
    s.measured_at,
    s.measured_date,
    s.source_quality,
    s.context_time_of_day,
    s.notes,
    COALESCE(v.measurement_value_count, 0)::int AS measurement_value_count,
    v.body_weight_value,
    v.body_weight_unit
FROM raw.body_measurement_sessions s
LEFT JOIN (
    SELECT
        measurement_session_id,
        COUNT(*) AS measurement_value_count,
        MAX(CASE WHEN measurement_type_canonical = 'body_weight' THEN value_numeric END) AS body_weight_value,
        MAX(CASE WHEN measurement_type_canonical = 'body_weight' THEN unit END) AS body_weight_unit
    FROM raw.body_measurement_values
    GROUP BY measurement_session_id
) v ON v.measurement_session_id = s.measurement_session_id
WHERE s.subject_profile_id = %(subject_profile_id)s
  {filter_clause}
ORDER BY s.measured_at DESC, s.measurement_session_id DESC
LIMIT %(limit)s
"""

TIMELINE_WORKOUTS_QUERY = """
SELECT
    workout_id,
    workout_date,
    session_sequence,
    title_raw,
    split_normalized,
    source_quality
FROM raw.workouts
WHERE 1 = 1
  {filter_clause}
ORDER BY workout_date DESC, session_sequence DESC, workout_id DESC
LIMIT %(limit)s
"""

CURRENT_PROFILE_QUERY = """
SELECT
    subject_profile_id,
    profile_kind,
    display_name,
    is_default,
    notes
FROM raw.subject_profiles
WHERE subject_profile_id = %(subject_profile_id)s
"""


def get_current_profile_overview() -> dict[str, object]:
    settings = get_settings()
    subject_profile_id = settings.default_subject_profile_id
    current_profile = _get_current_profile(subject_profile_id)
    recent_workouts = list_workouts(limit=5, offset=0, source_quality=None)["items"]
    recent_measurements = list_measurement_sessions(
        limit=5,
        offset=0,
        measurement_type=None,
        date_from=None,
        date_to=None,
        subject_profile_id=subject_profile_id,
    )["items"]
    latest_workout = recent_workouts[0] if recent_workouts else None
    latest_measurement = recent_measurements[0] if recent_measurements else None
    latest_workout_summary = (
        get_workout_summary(str(latest_workout["workout_id"])) if latest_workout else None
    )
    latest_measurements = get_latest_measurements(subject_profile_id=subject_profile_id)["items"]
    overdue = get_measurement_overdue(subject_profile_id=subject_profile_id)
    weekly_load_items = get_weekly_training_load(limit=4)["items"]
    cardio_items = get_cardio_analytics(limit=20)["items"]
    recovery_items = get_recovery_analytics(limit=20)["items"]

    latest_cardio_week = cardio_items[0]["week_start"] if cardio_items else None
    latest_recovery_week = recovery_items[0]["week_start"] if recovery_items else None

    return {
        "subject_profile": current_profile,
        "latest_workout": latest_workout,
        "latest_workout_summary": latest_workout_summary,
        "latest_measurement": latest_measurement,
        "latest_measurements": latest_measurements,
        "measurement_overdue": overdue,
        "weekly_workout_load_snapshot": weekly_load_items[0] if weekly_load_items else None,
        "recent_weekly_workout_load": weekly_load_items,
        "cardio_summary": {
            "latest_week_start": latest_cardio_week,
            "items": [
                row for row in cardio_items if row["week_start"] == latest_cardio_week
            ][:5],
        },
        "recovery_summary": {
            "latest_week_start": latest_recovery_week,
            "items": [
                row for row in recovery_items if row["week_start"] == latest_recovery_week
            ][:5],
        },
        "recent_workouts": recent_workouts,
        "recent_measurements": recent_measurements,
    }


def get_current_profile_timeline(
    *,
    limit: int,
    date_from: date | None,
    date_to: date | None,
    include_workouts: bool,
    include_measurements: bool,
) -> dict[str, object]:
    settings = get_settings()
    subject_profile_id = settings.default_subject_profile_id
    postgres = get_postgres_client()
    items: list[dict[str, object]] = []
    filters = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "include_workouts": include_workouts,
        "include_measurements": include_measurements,
    }

    if include_measurements:
        measurement_filter_clause, measurement_params = _build_date_filters(
            date_from=date_from,
            date_to=date_to,
            field_name="s.measured_date",
        )
        measurement_rows = normalize_records(
            postgres.fetch_all(
                TIMELINE_MEASUREMENTS_QUERY.format(filter_clause=measurement_filter_clause),
                {
                    "subject_profile_id": subject_profile_id,
                    "limit": limit,
                    **measurement_params,
                },
            )
        )
        for row in measurement_rows:
            items.append(
                {
                    "event_type": "measurement_session",
                    "event_id": row["measurement_session_id"],
                    "event_date": row["measured_date"],
                    "event_at": row["measured_at"],
                    "title": "Body measurement session",
                    "summary": {
                        "source_quality": row["source_quality"],
                        "context_time_of_day": row["context_time_of_day"],
                        "measurement_value_count": row["measurement_value_count"],
                        "body_weight_value": row["body_weight_value"],
                        "body_weight_unit": row["body_weight_unit"],
                        "notes": row["notes"],
                    },
                }
            )

    if include_workouts:
        workout_filter_clause, workout_params = _build_date_filters(
            date_from=date_from,
            date_to=date_to,
            field_name="workout_date",
        )
        workout_rows = normalize_records(
            postgres.fetch_all(
                TIMELINE_WORKOUTS_QUERY.format(filter_clause=workout_filter_clause),
                {"limit": limit, **workout_params},
            )
        )
        for row in workout_rows:
            synthetic_event_at = datetime.combine(
                date.fromisoformat(str(row["workout_date"])),
                time(hour=12, minute=0),
            ).isoformat()
            items.append(
                {
                    "event_type": "workout",
                    "event_id": row["workout_id"],
                    "event_date": row["workout_date"],
                    "event_at": synthetic_event_at,
                    "title": row["title_raw"],
                    "summary": {
                        "session_sequence": row["session_sequence"],
                        "split_normalized": row["split_normalized"],
                        "source_quality": row["source_quality"],
                    },
                }
            )

    items.sort(key=lambda row: (str(row["event_at"]), str(row["event_id"])), reverse=True)

    return {
        "subject_profile_id": subject_profile_id,
        "filters": filters,
        "items": items[:limit],
    }


def get_current_profile_progress_highlights() -> dict[str, object]:
    settings = get_settings()
    subject_profile_id = settings.default_subject_profile_id
    latest_measurements = get_latest_measurements(subject_profile_id=subject_profile_id)["items"]
    highlights = {
        measurement_type: next(
            (
                row
                for row in latest_measurements
                if row["measurement_type_canonical"] == measurement_type
            ),
            None,
        )
        for measurement_type in ("body_weight", "waist", "chest", "biceps")
    }
    recent_workouts = list_workouts(limit=4, offset=0, source_quality=None)["items"]
    last_workout = recent_workouts[0] if recent_workouts else None
    last_workout_summary = (
        get_workout_summary(str(last_workout["workout_id"])) if last_workout else None
    )

    return {
        "subject_profile_id": subject_profile_id,
        "measurement_highlights": highlights,
        "last_workout": last_workout,
        "last_workout_summary": last_workout_summary,
        "recent_workouts": recent_workouts,
        "measurement_overdue": get_measurement_overdue(subject_profile_id=subject_profile_id),
    }


def _get_current_profile(subject_profile_id: str) -> dict[str, object] | None:
    postgres = get_postgres_client()
    row = postgres.fetch_one(
        CURRENT_PROFILE_QUERY,
        {"subject_profile_id": subject_profile_id},
    )
    if row is None:
        return None
    return normalize_records([row])[0]


def _build_date_filters(
    *,
    date_from: date | None,
    date_to: date | None,
    field_name: str,
) -> tuple[str, dict[str, object]]:
    clauses: list[str] = []
    params: dict[str, object] = {}
    if date_from is not None:
        clauses.append(f"{field_name} >= %(date_from)s")
        params["date_from"] = date_from
    if date_to is not None:
        clauses.append(f"{field_name} <= %(date_to)s")
        params["date_to"] = date_to
    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params
