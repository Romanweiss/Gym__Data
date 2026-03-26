from app.core.config import get_settings
from app.db.clickhouse import get_clickhouse_client
from app.services.serialization import normalize_records


def get_weekly_training_load(limit: int) -> dict[str, object]:
    settings = get_settings()
    clickhouse = get_clickhouse_client()
    database = settings.clickhouse_database
    items = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                week_start,
                workouts_total,
                raw_detailed_workouts,
                partial_raw_workouts,
                summary_only_workouts,
                exercise_instances_total,
                set_count,
                total_reps,
                total_volume_kg,
                cardio_minutes,
                recovery_events_total,
                recovery_minutes
            FROM {database}.mart_weekly_training_load
            ORDER BY week_start DESC
            LIMIT %(limit)s
            """,
            params={"limit": limit},
        )
    )
    return {"items": items, "limit": limit}


def get_cardio_analytics(limit: int) -> dict[str, object]:
    settings = get_settings()
    clickhouse = get_clickhouse_client()
    database = settings.clickhouse_database
    items = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                week_start,
                machine,
                direction,
                workouts_total,
                segments_total,
                cardio_minutes
            FROM {database}.mart_cardio_summary
            ORDER BY week_start DESC, cardio_minutes DESC, machine ASC, direction ASC
            LIMIT %(limit)s
            """,
            params={"limit": limit},
        )
    )
    return {"items": items, "limit": limit}


def get_recovery_analytics(limit: int) -> dict[str, object]:
    settings = get_settings()
    clickhouse = get_clickhouse_client()
    database = settings.clickhouse_database
    items = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                week_start,
                event_type,
                workouts_total,
                recovery_events_total,
                recovery_minutes
            FROM {database}.mart_recovery_summary
            ORDER BY week_start DESC, recovery_events_total DESC, event_type ASC
            LIMIT %(limit)s
            """,
            params={"limit": limit},
        )
    )
    return {"items": items, "limit": limit}
