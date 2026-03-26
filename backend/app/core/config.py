from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GYM_DATA_", extra="ignore")

    app_name: str = "Gym__Data Backend"
    postgres_dsn: str = "postgresql://gym_data:gym_data@postgres:5432/gym_data"
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_database: str = "gym_data_mart"
    clickhouse_user: str = "gym_data"
    clickhouse_password: str = "gym_data"
    default_page_size: int = 50
    default_subject_profile_id: str = "subject_default"
    measurement_recommendation_cadence_days: int = 21
    workout_source_dir: Path = Path("/data/workouts/workouts")
    workout_schema_path: Path = Path("/data/workouts/schema/workout.schema.json")
    exercise_dictionary_path: Path = Path("/data/workouts/flat/exercise_dictionary.jsonl")
    measurement_source_dir: Path = Path("/data/measurements/measurements")
    measurement_flat_dir: Path = Path("/data/measurements/flat")
    measurement_schema_path: Path = Path("/data/measurements/schema/measurement_session.schema.json")
    measurement_type_dictionary_path: Path = Path("/data/measurements/flat/measurement_type_dictionary.jsonl")


@lru_cache
def get_settings() -> Settings:
    return Settings()
