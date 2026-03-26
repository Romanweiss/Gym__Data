from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    return value


def normalize_record(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    return {key: _normalize_value(value) for key, value in record.items()}


def normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_record(record) for record in records]

