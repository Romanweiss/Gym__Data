from app.db.postgres import get_postgres_client
from app.services.serialization import normalize_records


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
