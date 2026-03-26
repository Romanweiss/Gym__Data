from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from gym_data_ingestion.measurement_models import MeasurementFlattenedData


def write_measurement_flat_dataset(
    flat_dir: Path,
    dataset: MeasurementFlattenedData,
) -> None:
    flat_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(
        flat_dir / "subject_profiles.jsonl",
        [
            {
                "subject_profile_id": row["subject_profile_id"],
                "profile_kind": row["profile_kind"],
                "display_name": row["display_name"],
                "is_default": row["is_default"],
                "notes": row["notes"],
            }
            for row in dataset.subject_profiles
        ],
    )
    _write_jsonl(
        flat_dir / "measurement_type_dictionary.jsonl",
        [
            {
                "measurement_type_canonical": row["measurement_type_canonical"],
                "aliases": list(row["aliases"]),
                "default_unit": row["default_unit"],
                "category": row["category"],
                "sort_order": row["sort_order"],
                "value_kind": row["value_kind"],
            }
            for row in dataset.measurement_type_dictionary
        ],
    )
    _write_jsonl(
        flat_dir / "body_measurement_sessions.jsonl",
        [
            {
                "measurement_session_id": row["measurement_session_id"],
                "subject_profile_id": row["subject_profile_id"],
                "measured_at": row["measured_at"],
                "measured_date": row["measured_date"],
                "source_type": row["source_type"],
                "source_quality": row["source_quality"],
                "context_time_of_day": row["context_time_of_day"],
                "fasting_state": row["fasting_state"],
                "before_training": row["before_training"],
                "notes": row["notes"],
            }
            for row in dataset.body_measurement_sessions
        ],
    )
    _write_jsonl(
        flat_dir / "body_measurement_values.jsonl",
        [
            {
                "measurement_session_id": row["measurement_session_id"],
                "measurement_value_id": row["measurement_value_id"],
                "measurement_type_canonical": row["measurement_type_canonical"],
                "measurement_type_raw": row["measurement_type_raw"],
                "value_numeric": row["value_numeric"],
                "unit": row["unit"],
                "side_or_scope": row["side_or_scope"],
                "raw_value": row["raw_value"],
                "parse_note": row["parse_note"],
                "notes": row["notes"],
                "order_in_session": row["order_in_session"],
            }
            for row in dataset.body_measurement_values
        ],
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    rendered_rows = [
        json.dumps(_normalize_record(row), ensure_ascii=False, separators=(",", ":"))
        for row in rows
    ]
    content = "\n".join(rendered_rows)
    if rendered_rows:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in record.items()}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    return value
