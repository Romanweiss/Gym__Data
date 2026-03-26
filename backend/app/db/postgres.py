from functools import lru_cache
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row

from app.core.config import Settings, get_settings


class PostgresClient:
    def __init__(self, settings: Settings) -> None:
        self._dsn = settings.postgres_dsn

    def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with connect(self._dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or {})
                return list(cursor.fetchall())

    def fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with connect(self._dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or {})
                return cursor.fetchone()

    def ping(self) -> bool:
        record = self.fetch_one("SELECT 1 AS ok")
        return bool(record and record["ok"] == 1)


@lru_cache
def get_postgres_client() -> PostgresClient:
    return PostgresClient(get_settings())

