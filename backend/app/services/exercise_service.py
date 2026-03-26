from app.db.postgres import get_postgres_client
from app.services.serialization import normalize_records


COUNT_QUERY_TEMPLATE = """
SELECT COUNT(*)::int AS total
FROM raw.exercise_dictionary
{where_clause}
"""


LIST_QUERY_TEMPLATE = """
SELECT
    d.exercise_name_canonical,
    d.aliases,
    d.category,
    d.load_type,
    d.bodyweight_default,
    d.primary_muscles,
    COALESCE(stats.workout_count, 0)::int AS workout_count,
    COALESCE(stats.exercise_instance_count, 0)::int AS exercise_instance_count,
    COALESCE(stats.set_count, 0)::int AS set_count,
    stats.last_seen_date
FROM raw.exercise_dictionary d
LEFT JOIN (
    SELECT
        ei.exercise_name_canonical,
        COUNT(DISTINCT ei.workout_id) AS workout_count,
        COUNT(DISTINCT ei.exercise_instance_id) AS exercise_instance_count,
        COUNT(s.exercise_instance_id) AS set_count,
        MAX(w.workout_date) AS last_seen_date
    FROM raw.exercise_instances ei
    LEFT JOIN raw.sets s ON s.exercise_instance_id = ei.exercise_instance_id
    JOIN raw.workouts w ON w.workout_id = ei.workout_id
    GROUP BY ei.exercise_name_canonical
) stats ON stats.exercise_name_canonical = d.exercise_name_canonical
{where_clause}
ORDER BY COALESCE(stats.workout_count, 0) DESC, d.exercise_name_canonical ASC
LIMIT %(limit)s OFFSET %(offset)s
"""


def list_exercises(limit: int, offset: int, category: str | None) -> dict[str, object]:
    postgres = get_postgres_client()
    params = {"limit": limit, "offset": offset}
    where_clause = ""
    if category is not None:
        where_clause = "WHERE d.category = %(category)s"
        params["category"] = category

    count_where_clause = ""
    count_params: dict[str, object] = {}
    if category is not None:
        count_where_clause = "WHERE category = %(category)s"
        count_params["category"] = category

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
            "category": category,
        },
    }
