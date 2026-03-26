from app.core.config import get_settings
from app.db.clickhouse import get_clickhouse_client
from app.services.serialization import normalize_record, normalize_records

def get_summary() -> dict[str, object]:
    settings = get_settings()
    database = settings.clickhouse_database
    clickhouse = get_clickhouse_client()
    totals = normalize_record(
        clickhouse.fetch_one(
            f"""
            SELECT
                count() AS workouts_total,
                ifNull(sum(set_count), 0) AS set_count,
                ifNull(sum(total_reps), 0) AS total_reps,
                round(ifNull(sum(total_volume_kg), 0), 2) AS total_volume_kg,
                ifNull(sum(cardio_minutes), 0) AS cardio_minutes,
                ifNull(sum(recovery_minutes), 0) AS recovery_minutes
            FROM {database}.mart_workout_summary
            """
        )
    )
    quality_breakdown = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                source_quality,
                count() AS workouts_total,
                ifNull(sum(set_count), 0) AS set_count,
                round(ifNull(sum(total_volume_kg), 0), 2) AS total_volume_kg
            FROM {database}.mart_workout_summary
            GROUP BY source_quality
            ORDER BY workouts_total DESC, source_quality ASC
            """
        )
    )
    daily_rollup = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                workout_date,
                workouts_total,
                set_count,
                total_reps,
                total_volume_kg,
                cardio_minutes,
                recovery_minutes
            FROM {database}.v_daily_workout_rollup
            ORDER BY workout_date DESC
            """
        )
    )
    top_exercises = normalize_records(
        clickhouse.fetch_all(
            f"""
            SELECT
                exercise_name_canonical,
                category,
                load_type,
                workout_appearances,
                tracked_workout_appearances,
                set_count,
                total_reps,
                total_volume_kg,
                max_weight_kg,
                last_seen_date
            FROM {database}.v_exercise_rollup
            ORDER BY tracked_workout_appearances DESC, set_count DESC, exercise_name_canonical ASC
            LIMIT 10
            """
        )
    )

    return {
        "totals": totals,
        "quality_breakdown": quality_breakdown,
        "daily_rollup": daily_rollup,
        "top_exercises": top_exercises,
    }
