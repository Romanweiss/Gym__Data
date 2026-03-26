from functools import lru_cache
from typing import Any

import clickhouse_connect

from app.core.config import Settings, get_settings


class ClickHouseClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _get_client(self):
        return clickhouse_connect.get_client(
            host=self._settings.clickhouse_host,
            port=self._settings.clickhouse_port,
            username=self._settings.clickhouse_user,
            password=self._settings.clickhouse_password,
            database=self._settings.clickhouse_database,
        )

    def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        client = self._get_client()
        try:
            result = client.query(query, parameters=params or {})
            return [dict(zip(result.column_names, row)) for row in result.result_rows]
        finally:
            client.close()

    def fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = self.fetch_all(query, params=params)
        return rows[0] if rows else None

    def ping(self) -> bool:
        client = self._get_client()
        try:
            return str(client.command("SELECT 1")).strip() == "1"
        finally:
            client.close()


@lru_cache
def get_clickhouse_client() -> ClickHouseClient:
    return ClickHouseClient(get_settings())
