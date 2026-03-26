from datetime import date

from app.core.config import get_settings
from app.db.clickhouse import get_clickhouse_client
from app.db.postgres import get_postgres_client
from app.services.serialization import normalize_record, normalize_records

LIST_COUNT_QUERY = """
SELECT COUNT(*)::int AS total
FROM raw.body_measurement_sessions s
{where_clause}
"""

LIST_QUERY = """
SELECT
    s.measurement_session_id,
    s.subject_profile_id,
    s.measured_at,
    s.measured_date,
    s.source_type,
    s.source_quality,
    s.context_time_of_day,
    s.fasting_state,
    s.before_training,
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
{where_clause}
ORDER BY s.measured_at DESC, s.measurement_session_id DESC
LIMIT %(limit)s OFFSET %(offset)s
"""

DETAIL_SESSION_QUERY = """
SELECT
    s.measurement_session_id,
    s.subject_profile_id,
    p.profile_kind,
    p.display_name,
    p.is_default,
    s.measured_at,
    s.measured_date,
    s.source_type,
    s.source_quality,
    s.context_time_of_day,
    s.fasting_state,
    s.before_training,
    s.notes
FROM raw.body_measurement_sessions s
JOIN raw.subject_profiles p ON p.subject_profile_id = s.subject_profile_id
WHERE s.measurement_session_id = %(measurement_session_id)s
"""

DETAIL_VALUES_QUERY = """
SELECT
    v.measurement_value_id,
    v.measurement_type_canonical,
    v.measurement_type_raw,
    v.value_numeric,
    v.unit,
    v.side_or_scope,
    v.raw_value,
    v.parse_note,
    v.notes,
    v.order_in_session,
    d.category,
    d.value_kind,
    d.sort_order
FROM raw.body_measurement_values v
JOIN raw.measurement_type_dictionary d
  ON d.measurement_type_canonical = v.measurement_type_canonical
WHERE v.measurement_session_id = %(measurement_session_id)s
ORDER BY v.order_in_session ASC, d.sort_order ASC
"""

LATEST_QUERY = """
SELECT
    subject_profile_id,
    measurement_type_canonical,
    category,
    value_kind,
    sort_order,
    unit,
    latest_measurement_session_id,
    latest_measured_at,
    latest_measured_date,
    latest_value_numeric,
    previous_measurement_session_id,
    previous_measured_date,
    previous_value_numeric,
    delta_value_numeric,
    days_since_previous
FROM {database}.mart_measurement_latest
WHERE subject_profile_id = %(subject_profile_id)s
ORDER BY sort_order ASC, measurement_type_canonical ASC
"""

PROGRESS_QUERY_TEMPLATE = """
SELECT
    subject_profile_id,
    measurement_session_id,
    measured_at,
    measured_date,
    measurement_type_canonical,
    measurement_type_raw,
    category,
    value_kind,
    sort_order,
    unit,
    side_or_scope,
    source_quality,
    context_time_of_day,
    value_numeric,
    previous_measurement_session_id,
    previous_measured_date,
    previous_value_numeric,
    delta_value_numeric,
    days_since_previous,
    workouts_since_previous_measurement,
    total_sets_since_previous_measurement,
    total_reps_since_previous_measurement,
    total_volume_kg_since_previous_measurement,
    cardio_minutes_since_previous_measurement,
    recovery_minutes_since_previous_measurement
FROM {database}.mart_measurement_progress
WHERE subject_profile_id = %(subject_profile_id)s
  {filter_clause}
ORDER BY measured_date ASC, sort_order ASC, measurement_session_id ASC
"""


def list_measurement_sessions(
    limit: int,
    offset: int,
    measurement_type: str | None,
    date_from: date | None,
    date_to: date | None,
    subject_profile_id: str | None,
) -> dict[str, object]:
    postgres = get_postgres_client()
    params: dict[str, object] = {"limit": limit, "offset": offset}
    where_clause, where_params = _build_session_filters(
        measurement_type=measurement_type,
        date_from=date_from,
        date_to=date_to,
        subject_profile_id=subject_profile_id,
        session_alias="s",
    )
    params.update(where_params)

    total_record = postgres.fetch_one(
        LIST_COUNT_QUERY.format(where_clause=where_clause),
        where_params,
    ) or {"total": 0}
    items = normalize_records(
        postgres.fetch_all(
            LIST_QUERY.format(where_clause=where_clause),
            params,
        )
    )

    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_record["total"],
        },
        "filters": {
            "measurement_type": measurement_type,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "subject_profile_id": subject_profile_id,
        },
    }


def get_measurement_session_detail(measurement_session_id: str) -> dict[str, object] | None:
    postgres = get_postgres_client()
    session = normalize_record(
        postgres.fetch_one(
            DETAIL_SESSION_QUERY,
            {"measurement_session_id": measurement_session_id},
        )
    )
    if not session:
        return None

    values = normalize_records(
        postgres.fetch_all(
            DETAIL_VALUES_QUERY,
            {"measurement_session_id": measurement_session_id},
        )
    )
    return {
        "measurement_session_id": session["measurement_session_id"],
        "subject_profile": {
            "subject_profile_id": session["subject_profile_id"],
            "profile_kind": session["profile_kind"],
            "display_name": session["display_name"],
            "is_default": session["is_default"],
        },
        "measured_at": session["measured_at"],
        "measured_date": session["measured_date"],
        "source_type": session["source_type"],
        "source_quality": session["source_quality"],
        "context_time_of_day": session["context_time_of_day"],
        "fasting_state": session["fasting_state"],
        "before_training": session["before_training"],
        "notes": session["notes"],
        "measurements": values,
    }


def get_latest_measurements(subject_profile_id: str | None) -> dict[str, object]:
    settings = get_settings()
    resolved_subject_profile_id = subject_profile_id or settings.default_subject_profile_id
    clickhouse = get_clickhouse_client()
    items = normalize_records(
        clickhouse.fetch_all(
            LATEST_QUERY.format(database=settings.clickhouse_database),
            params={"subject_profile_id": resolved_subject_profile_id},
        )
    )
    return {
        "subject_profile_id": resolved_subject_profile_id,
        "items": items,
    }


def get_measurement_progress(
    subject_profile_id: str | None,
    measurement_type: str | None,
    date_from: date | None,
    date_to: date | None,
) -> dict[str, object]:
    settings = get_settings()
    resolved_subject_profile_id = subject_profile_id or settings.default_subject_profile_id
    clickhouse = get_clickhouse_client()
    filter_clauses: list[str] = []
    params: dict[str, object] = {"subject_profile_id": resolved_subject_profile_id}
    if measurement_type:
        filter_clauses.append("measurement_type_canonical = %(measurement_type)s")
        params["measurement_type"] = measurement_type
    if date_from:
        filter_clauses.append("measured_date >= %(date_from)s")
        params["date_from"] = date_from.isoformat()
    if date_to:
        filter_clauses.append("measured_date <= %(date_to)s")
        params["date_to"] = date_to.isoformat()

    filter_clause = ""
    if filter_clauses:
        filter_clause = " AND " + " AND ".join(filter_clauses)

    items = normalize_records(
        clickhouse.fetch_all(
            PROGRESS_QUERY_TEMPLATE.format(
                database=settings.clickhouse_database,
                filter_clause=filter_clause,
            ),
            params=params,
        )
    )
    return {
        "subject_profile_id": resolved_subject_profile_id,
        "filters": {
            "measurement_type": measurement_type,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "items": items,
    }


def get_measurement_overdue(subject_profile_id: str | None) -> dict[str, object]:
    settings = get_settings()
    resolved_subject_profile_id = subject_profile_id or settings.default_subject_profile_id
    postgres = get_postgres_client()

    latest_session = normalize_record(
        postgres.fetch_one(
            """
            SELECT
                measurement_session_id,
                subject_profile_id,
                measured_at,
                measured_date
            FROM raw.body_measurement_sessions
            WHERE subject_profile_id = %(subject_profile_id)s
            ORDER BY measured_at DESC, measurement_session_id DESC
            LIMIT 1
            """,
            {"subject_profile_id": resolved_subject_profile_id},
        )
    )

    if not latest_session:
        workouts_total = normalize_record(
            postgres.fetch_one(
                """
                SELECT COUNT(*)::int AS workouts_total
                FROM raw.workouts
                """
            )
        ) or {"workouts_total": 0}
        return {
            "subject_profile_id": resolved_subject_profile_id,
            "cadence_days": settings.measurement_recommendation_cadence_days,
            "last_measurement_session_id": None,
            "last_measurement_date": None,
            "days_since_last_measurement": None,
            "workouts_since_last_measurement": workouts_total["workouts_total"],
            "last_workout_date": None,
            "recommended_now": True,
            "recommendation_reason": "No body measurements recorded yet.",
        }

    last_measurement_date = date.fromisoformat(str(latest_session["measured_date"]))
    workouts_since = normalize_record(
        postgres.fetch_one(
            """
            SELECT
                COUNT(*)::int AS workouts_since_last_measurement,
                MAX(workout_date) AS last_workout_date
            FROM raw.workouts
            WHERE workout_date > %(last_measurement_date)s
            """,
            {"last_measurement_date": last_measurement_date},
        )
    ) or {
        "workouts_since_last_measurement": 0,
        "last_workout_date": None,
    }

    days_since_last_measurement = (date.today() - last_measurement_date).days
    recommended_now = days_since_last_measurement >= settings.measurement_recommendation_cadence_days
    recommendation_reason = (
        f"Last measurement is {days_since_last_measurement} days old; cadence threshold is {settings.measurement_recommendation_cadence_days} days."
        if recommended_now
        else f"Last measurement is within the configured {settings.measurement_recommendation_cadence_days}-day cadence."
    )

    return {
        "subject_profile_id": resolved_subject_profile_id,
        "cadence_days": settings.measurement_recommendation_cadence_days,
        "last_measurement_session_id": latest_session["measurement_session_id"],
        "last_measurement_date": latest_session["measured_date"],
        "days_since_last_measurement": days_since_last_measurement,
        "workouts_since_last_measurement": workouts_since["workouts_since_last_measurement"],
        "last_workout_date": workouts_since["last_workout_date"],
        "recommended_now": recommended_now,
        "recommendation_reason": recommendation_reason,
    }


def _build_session_filters(
    measurement_type: str | None,
    date_from: date | None,
    date_to: date | None,
    subject_profile_id: str | None,
    session_alias: str,
) -> tuple[str, dict[str, object]]:
    clauses: list[str] = []
    params: dict[str, object] = {}

    if subject_profile_id:
        clauses.append(f"{session_alias}.subject_profile_id = %(subject_profile_id)s")
        params["subject_profile_id"] = subject_profile_id
    if date_from:
        clauses.append(f"{session_alias}.measured_date >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        clauses.append(f"{session_alias}.measured_date <= %(date_to)s")
        params["date_to"] = date_to
    if measurement_type:
        clauses.append(
            f"""
            EXISTS (
                SELECT 1
                FROM raw.body_measurement_values mv
                WHERE mv.measurement_session_id = {session_alias}.measurement_session_id
                  AND mv.measurement_type_canonical = %(measurement_type)s
            )
            """
        )
        params["measurement_type"] = measurement_type

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params
