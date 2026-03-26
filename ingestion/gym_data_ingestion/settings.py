from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GYM_DATA_", extra="ignore")

    postgres_dsn: str = "postgresql://gym_data:gym_data@postgres:5432/gym_data"
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_database: str = "gym_data_mart"
    clickhouse_user: str = "gym_data"
    clickhouse_password: str = "gym_data"
    workout_data_root: Path = Path("/data/workouts")
    workout_source_dir: Path = Path("/data/workouts/workouts")
    workout_schema_path: Path = Path("/data/workouts/schema/workout.schema.json")
    exercise_dictionary_path: Path = Path("/data/workouts/flat/exercise_dictionary.jsonl")


@lru_cache
def get_settings() -> Settings:
    return Settings()

