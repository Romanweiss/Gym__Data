from app.core.config import get_settings
from app.db.clickhouse import get_clickhouse_client
from app.db.postgres import get_postgres_client
from app.services.serialization import normalize_record, normalize_records

COUNT_QUERY_TEMPLATE = """
SELECT COUNT(*)::int AS total
FROM raw.workouts
{where_clause}
"""

LIST_QUERY_TEMPLATE = """
SELECT
    w.workout_id,
    w.workout_date,
    w.session_sequence,
    w.title_raw,
    w.split_raw,
    w.split_normalized,
    w.source_quality,
    COALESCE(e.exercise_count, 0)::int AS exercise_count,
    COALESCE(s.set_count, 0)::int AS set_count,
    COALESCE(s.total_volume_kg, 0) AS total_volume_kg,
    COALESCE(c.cardio_minutes, 0)::int AS cardio_minutes,
    COALESCE(r.recovery_event_count, 0)::int AS recovery_event_count
FROM raw.workouts w
LEFT JOIN (
    SELECT workout_id, COUNT(*) AS exercise_count
    FROM raw.exercise_instances
    GROUP BY workout_id
) e ON e.workout_id = w.workout_id
LEFT JOIN (
    SELECT workout_id, COUNT(*) AS set_count, SUM(weight_kg * reps) AS total_volume_kg
    FROM raw.sets
    GROUP BY workout_id
) s ON s.workout_id = w.workout_id
LEFT JOIN (
    SELECT workout_id, COALESCE(SUM(duration_min), 0) AS cardio_minutes
    FROM raw.cardio_segments
    GROUP BY workout_id
) c ON c.workout_id = w.workout_id
LEFT JOIN (
    SELECT workout_id, COUNT(*) AS recovery_event_count
    FROM raw.recovery_events
    GROUP BY workout_id
) r ON r.workout_id = w.workout_id
{where_clause}
ORDER BY w.workout_date DESC, w.session_sequence DESC, w.workout_id DESC
LIMIT %(limit)s OFFSET %(offset)s
"""

DETAIL_WORKOUT_QUERY = """
SELECT
    workout_id,
    workout_date,
    session_sequence,
    title_raw,
    split_raw,
    split_normalized,
    source_type,
    source_quality,
    source_text,
    notes
FROM raw.workouts
WHERE workout_id = %(workout_id)s
"""

DETAIL_CARDIO_QUERY = """
SELECT
    segment_order,
    machine,
    direction,
    duration_min,
    notes
FROM raw.cardio_segments
WHERE workout_id = %(workout_id)s
ORDER BY segment_order ASC
"""

DETAIL_RECOVERY_QUERY = """
SELECT
    event_order,
    event_type,
    duration_min,
    notes
FROM raw.recovery_events
WHERE workout_id = %(workout_id)s
ORDER BY event_order ASC
"""

DETAIL_EXERCISES_QUERY = """
SELECT
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
    source_quality
FROM raw.exercise_instances
WHERE workout_id = %(workout_id)s
ORDER BY exercise_order ASC, exercise_instance_id ASC
"""

DETAIL_SETS_QUERY = """
SELECT
    exercise_instance_id,
    set_order,
    weight_kg,
    reps,
    raw_value,
    parse_note
FROM raw.sets
WHERE workout_id = %(workout_id)s
ORDER BY exercise_instance_id ASC, set_order ASC
"""


def list_workouts(limit: int, offset: int, source_quality: str | None) -> dict[str, object]:
    postgres = get_postgres_client()
    params = {"limit": limit, "offset": offset}
    where_clause = ""
    if source_quality is not None:
        where_clause = "WHERE w.source_quality = %(source_quality)s"
        params["source_quality"] = source_quality

    count_where_clause = ""
    count_params: dict[str, object] = {}
    if source_quality is not None:
        count_where_clause = "WHERE source_quality = %(source_quality)s"
        count_params["source_quality"] = source_quality

    total_record = postgres.fetch_one(
        COUNT_QUERY_TEMPLATE.format(where_clause=count_where_clause),
        count_params,
    ) or {"total": 0}
    items = normalize_records(
        postgres.fetch_all(
            LIST_QUERY_TEMPLATE.format(where_clause=where_clause),
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
            "source_quality": source_quality,
        },
    }


def get_workout_detail(workout_id: str) -> dict[str, object] | None:
    postgres = get_postgres_client()
    workout = postgres.fetch_one(DETAIL_WORKOUT_QUERY, {"workout_id": workout_id})
    if workout is None:
        return None

    cardio_segments = normalize_records(
        postgres.fetch_all(DETAIL_CARDIO_QUERY, {"workout_id": workout_id})
    )
    recovery_events = normalize_records(
        postgres.fetch_all(DETAIL_RECOVERY_QUERY, {"workout_id": workout_id})
    )
    exercise_rows = normalize_records(
        postgres.fetch_all(DETAIL_EXERCISES_QUERY, {"workout_id": workout_id})
    )
    set_rows = normalize_records(
        postgres.fetch_all(DETAIL_SETS_QUERY, {"workout_id": workout_id})
    )

    sets_by_exercise: dict[str, list[dict[str, object]]] = {}
    for set_row in set_rows:
        sets_by_exercise.setdefault(str(set_row["exercise_instance_id"]), []).append(
            {
                "set_order": int(set_row["set_order"]),
                "weight_kg": set_row["weight_kg"],
                "reps": int(set_row["reps"]),
                "raw_value": set_row["raw_value"],
                "parse_note": set_row["parse_note"],
            }
        )

    exercise_instances: list[dict[str, object]] = []
    for exercise in exercise_rows:
        exercise_instance_id = str(exercise["exercise_instance_id"])
        exercise_instances.append(
            {
                "exercise_instance_id": exercise_instance_id,
                "display_order": _display_order(exercise_instance_id),
                "source_order": exercise["exercise_order"],
                "exercise_name_raw": exercise["exercise_name_raw"],
                "exercise_name_canonical": exercise["exercise_name_canonical"],
                "category": exercise["category"],
                "load_type": exercise["load_type"],
                "bodyweight": bool(exercise["bodyweight"]),
                "attributes": exercise["attributes"],
                "raw_sets_text": exercise["raw_sets_text"],
                "notes": exercise["notes"],
                "source_quality": exercise["source_quality"],
                "sets": sets_by_exercise.get(exercise_instance_id, []),
            }
        )

    workout_record = normalize_record(workout)
    return {
        "workout_id": workout_record["workout_id"],
        "date": workout_record["workout_date"],
        "session_sequence": workout_record["session_sequence"],
        "title_raw": workout_record["title_raw"],
        "split_raw": workout_record["split_raw"],
        "split_normalized": workout_record["split_normalized"],
        "source_type": workout_record["source_type"],
        "source_quality": workout_record["source_quality"],
        "source_text": workout_record["source_text"],
        "notes": workout_record["notes"],
        "cardio_segments": [
            {
                "order": int(row["segment_order"]),
                "machine": row["machine"],
                "direction": row["direction"],
                "duration_min": row["duration_min"],
                "notes": row["notes"],
            }
            for row in cardio_segments
        ],
        "recovery_events": [
            {
                "order": int(row["event_order"]),
                "event_type": row["event_type"],
                "duration_min": row["duration_min"],
                "notes": row["notes"],
            }
            for row in recovery_events
        ],
        "exercise_instances": exercise_instances,
    }


def get_workout_summary(workout_id: str) -> dict[str, object] | None:
    settings = get_settings()
    clickhouse = get_clickhouse_client()
    return normalize_record(
        clickhouse.fetch_one(
            f"""
            SELECT
                workout_id,
                workout_date,
                session_sequence,
                source_quality,
                title_raw,
                split_normalized,
                exercise_count,
                tracked_exercise_count,
                distinct_canonical_exercise_count,
                bodyweight_exercise_count,
                bodyweight_set_count,
                set_count,
                total_reps,
                total_volume_kg,
                cardio_segments_count,
                cardio_minutes,
                recovery_events_count,
                recovery_minutes
            FROM {settings.clickhouse_database}.mart_workout_detail_rollup
            WHERE workout_id = %(workout_id)s
            """,
            params={"workout_id": workout_id},
        )
    ) or None


def _display_order(exercise_instance_id: str) -> int:
    return int(exercise_instance_id.rsplit("_ex_", 1)[1])
