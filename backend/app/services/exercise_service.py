from app.core.config import get_settings
from app.db.clickhouse import get_clickhouse_client
from app.db.postgres import get_postgres_client
from app.services.serialization import normalize_record, normalize_records

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

EXERCISE_DIMENSION_QUERY = """
SELECT
    exercise_name_canonical,
    aliases,
    category,
    load_type,
    bodyweight_default,
    primary_muscles
FROM raw.exercise_dictionary
WHERE exercise_name_canonical = %(exercise_name_canonical)s
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


def get_exercise_progress(exercise_name_canonical: str) -> dict[str, object] | None:
    postgres = get_postgres_client()
    dimension = normalize_record(
        postgres.fetch_one(
            EXERCISE_DIMENSION_QUERY,
            {"exercise_name_canonical": exercise_name_canonical},
        )
    )
    if not dimension:
        return None

    settings = get_settings()
    clickhouse = get_clickhouse_client()
    database = settings.clickhouse_database

    summary = normalize_record(
        clickhouse.fetch_one(
            f"""
            SELECT
                exercise_name_canonical,
                category,
                load_type,
                primary_muscles,
                workout_appearances,
                tracked_workout_appearances,
                set_count,
                total_reps,
                total_volume_kg,
                max_weight_kg,
                max_reps_in_set,
                first_performed_date,
                last_performed_date
            FROM {database}.v_exercise_progress_rollup
            WHERE exercise_name_canonical = %(exercise_name_canonical)s
            """,
            params={"exercise_name_canonical": exercise_name_canonical},
        )
    )

    history = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                workout_date,
                workout_id,
                session_sequence,
                exercise_instance_id,
                display_order,
                exercise_order,
                source_quality,
                split_normalized,
                set_count,
                total_reps,
                total_volume_kg,
                max_weight_kg,
                max_reps_in_set
            FROM {database}.mart_exercise_progress
            WHERE exercise_name_canonical = %(exercise_name_canonical)s
            ORDER BY workout_date DESC, workout_id DESC, display_order ASC
            """,
            params={"exercise_name_canonical": exercise_name_canonical},
        )
    )

    split_frequency = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                split_tag,
                appearances
            FROM
            (
                SELECT
                    arrayJoin(split_normalized) AS split_tag,
                    count() AS appearances
                FROM {database}.mart_exercise_progress
                WHERE exercise_name_canonical = %(exercise_name_canonical)s
                GROUP BY split_tag
            )
            ORDER BY appearances DESC, split_tag ASC
            """,
            params={"exercise_name_canonical": exercise_name_canonical},
        )
    )

    return {
        "exercise": dimension,
        "progress_summary": summary,
        "split_frequency": split_frequency,
        "history": history,
    }
