from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from gym_data_ingestion.models import DatasetValidationError, Record, SourceDocument

MEASUREMENT_SOURCE_QUALITY_VALUES = {"measured_direct", "self_reported", "imported_record"}
MEASUREMENT_CONTEXT_TIME_OF_DAY_VALUES = {"morning", "unknown", "other"}
MEASUREMENT_VALUE_KIND_VALUES = {"circumference", "weight"}
UNIT_DEFAULTED_PARSE_NOTE = "unit_defaulted_from_measurement_type"


@dataclass
class MeasurementFlattenedData:
    subject_profiles: list[Record] = field(default_factory=list)
    body_measurement_sessions: list[Record] = field(default_factory=list)
    body_measurement_values: list[Record] = field(default_factory=list)
    measurement_type_dictionary: list[Record] = field(default_factory=list)
    source_files: list[Record] = field(default_factory=list)


def build_flattened_measurement_dataset(
    documents: list[SourceDocument],
    measurement_type_dictionary_path: Path,
    default_subject_profile_id: str,
) -> MeasurementFlattenedData:
    dictionary_rows, alias_to_canonical = _load_measurement_type_dictionary(
        measurement_type_dictionary_path
    )
    dictionary_by_canonical = {
        row["measurement_type_canonical"]: row for row in dictionary_rows
    }

    dataset = MeasurementFlattenedData()
    dataset.measurement_type_dictionary = dictionary_rows

    subject_profiles: dict[str, Record] = {
        default_subject_profile_id: _default_subject_profile(default_subject_profile_id)
    }
    seen_session_ids: set[str] = set()

    for document in documents:
        payload = document.payload
        measurement_session_id = str(payload["measurement_session_id"])
        if document.file_path.stem != measurement_session_id:
            raise DatasetValidationError(
                f"Measurement file name {document.file_path.name} does not match measurement_session_id {measurement_session_id}."
            )
        if measurement_session_id in seen_session_ids:
            raise DatasetValidationError(
                f"Duplicate measurement_session_id detected: {measurement_session_id}"
            )
        seen_session_ids.add(measurement_session_id)

        subject_profile_id = str(payload.get("subject_profile_id") or default_subject_profile_id)
        if subject_profile_id not in subject_profiles:
            subject_profiles[subject_profile_id] = _derived_subject_profile(subject_profile_id)

        measured_at = datetime.fromisoformat(str(payload["measured_at"]))
        source_quality = _validated_source_quality(str(payload["source_quality"]))
        context_time_of_day = _validated_context_time_of_day(
            str(payload["context_time_of_day"])
        )
        measurements = payload.get("measurements", [])
        if not measurements:
            raise DatasetValidationError(
                f"Measurement session {measurement_session_id} must contain at least one measurement value."
            )

        dataset.body_measurement_sessions.append(
            {
                "measurement_session_id": measurement_session_id,
                "subject_profile_id": subject_profile_id,
                "measured_at": measured_at,
                "measured_date": measured_at.date(),
                "source_type": payload.get("source_type"),
                "source_quality": source_quality,
                "context_time_of_day": context_time_of_day,
                "fasting_state": payload.get("fasting_state"),
                "before_training": payload.get("before_training"),
                "notes": payload.get("notes"),
                "raw_payload": payload,
            }
        )
        dataset.source_files.append(
            {
                "file_path": document.relative_path,
                "measurement_session_id": measurement_session_id,
                "subject_profile_id": subject_profile_id,
                "source_quality": source_quality,
                "file_sha256": document.file_sha256,
            }
        )

        seen_orders: set[int] = set()
        seen_type_scope: set[tuple[str, str]] = set()
        for measurement in measurements:
            order_in_session = int(measurement["order_in_session"])
            if order_in_session in seen_orders:
                raise DatasetValidationError(
                    f"Measurement session {measurement_session_id} contains duplicate order_in_session {order_in_session}."
                )
            seen_orders.add(order_in_session)

            measurement_type_raw = str(measurement["measurement_type_raw"])
            raw_alias = measurement_type_raw.strip().lower()
            measurement_type_canonical = alias_to_canonical.get(raw_alias)
            if measurement_type_canonical is None:
                raise DatasetValidationError(
                    f"Measurement session {measurement_session_id} contains unsupported measurement_type_raw {measurement_type_raw!r}."
                )

            side_or_scope = measurement.get("side_or_scope")
            logical_key = (measurement_type_canonical, str(side_or_scope or ""))
            if logical_key in seen_type_scope:
                raise DatasetValidationError(
                    f"Measurement session {measurement_session_id} duplicates measurement {logical_key}."
                )
            seen_type_scope.add(logical_key)

            dictionary_row = dictionary_by_canonical[measurement_type_canonical]
            default_unit = str(dictionary_row["default_unit"])
            input_unit = measurement.get("unit")
            parse_note = None
            if input_unit in (None, ""):
                unit = default_unit
                parse_note = UNIT_DEFAULTED_PARSE_NOTE
            else:
                unit = str(input_unit)

            if unit != default_unit:
                raise DatasetValidationError(
                    f"Measurement session {measurement_session_id} uses unsupported unit {unit!r} for {measurement_type_canonical}; expected {default_unit!r}."
                )

            value_numeric = Decimal(str(measurement["value_numeric"]))
            if value_numeric <= 0:
                raise DatasetValidationError(
                    f"Measurement session {measurement_session_id} contains non-positive value for {measurement_type_canonical}."
                )

            measurement_value_id = f"{measurement_session_id}_mv_{order_in_session:02d}"
            dataset.body_measurement_values.append(
                {
                    "measurement_value_id": measurement_value_id,
                    "measurement_session_id": measurement_session_id,
                    "measurement_type_canonical": measurement_type_canonical,
                    "measurement_type_raw": measurement_type_raw,
                    "value_numeric": float(value_numeric),
                    "unit": unit,
                    "side_or_scope": side_or_scope,
                    "raw_value": measurement.get("raw_value"),
                    "parse_note": parse_note,
                    "notes": measurement.get("notes"),
                    "order_in_session": order_in_session,
                    "raw_payload": measurement,
                }
            )

        _validate_dense_order_sequence(
            actual_orders=seen_orders,
            expected_owner=f"measurement session {measurement_session_id} values",
        )

    dataset.subject_profiles = [
        subject_profiles[subject_profile_id]
        for subject_profile_id in sorted(subject_profiles)
    ]
    return dataset


def _load_measurement_type_dictionary(
    measurement_type_dictionary_path: Path,
) -> tuple[list[Record], dict[str, str]]:
    if not measurement_type_dictionary_path.exists():
        raise DatasetValidationError(
            f"Measurement type dictionary is missing: {measurement_type_dictionary_path}"
        )

    rows: list[Record] = []
    alias_to_canonical: dict[str, str] = {}
    seen_canonicals: set[str] = set()

    for line in measurement_type_dictionary_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        canonical = str(row["measurement_type_canonical"])
        if canonical in seen_canonicals:
            raise DatasetValidationError(
                f"Duplicate measurement type dictionary row: {canonical}"
            )
        seen_canonicals.add(canonical)

        default_unit = str(row["default_unit"])
        category = str(row["category"])
        sort_order = int(row["sort_order"])
        value_kind = str(row["value_kind"])
        if value_kind not in MEASUREMENT_VALUE_KIND_VALUES:
            raise DatasetValidationError(
                f"Unsupported measurement value_kind {value_kind!r} for {canonical}."
            )

        aliases = sorted(
            {str(alias).strip() for alias in row.get("aliases", []) if str(alias).strip()}
        )

        for alias in aliases + [canonical]:
            alias_key = alias.lower()
            existing = alias_to_canonical.get(alias_key)
            if existing is not None and existing != canonical:
                raise DatasetValidationError(
                    f"Measurement alias {alias!r} maps to multiple canonical values: {existing} and {canonical}."
                )
            alias_to_canonical[alias_key] = canonical

        rows.append(
            {
                "measurement_type_canonical": canonical,
                "aliases": aliases,
                "default_unit": default_unit,
                "category": category,
                "sort_order": sort_order,
                "value_kind": value_kind,
                "source_payload": row,
            }
        )

    return sorted(rows, key=lambda row: int(row["sort_order"])), alias_to_canonical


def _default_subject_profile(default_subject_profile_id: str) -> Record:
    return {
        "subject_profile_id": default_subject_profile_id,
        "profile_kind": "person_placeholder",
        "display_name": "Default single-user profile",
        "is_default": True,
        "notes": "Stage 1.2 placeholder profile for single-user mode.",
        "source_payload": {
            "source": "stage_1_2_default",
            "future_migration_target": "client_or_user_profile",
        },
    }


def _derived_subject_profile(subject_profile_id: str) -> Record:
    return {
        "subject_profile_id": subject_profile_id,
        "profile_kind": "person_placeholder",
        "display_name": subject_profile_id,
        "is_default": False,
        "notes": "Derived from measurement source documents.",
        "source_payload": {
            "source": "derived_from_measurements",
        },
    }


def _validated_source_quality(source_quality: str) -> str:
    if source_quality not in MEASUREMENT_SOURCE_QUALITY_VALUES:
        raise DatasetValidationError(f"Unsupported measurement source_quality: {source_quality}")
    return source_quality


def _validated_context_time_of_day(context_time_of_day: str) -> str:
    if context_time_of_day not in MEASUREMENT_CONTEXT_TIME_OF_DAY_VALUES:
        raise DatasetValidationError(
            f"Unsupported context_time_of_day: {context_time_of_day}"
        )
    return context_time_of_day


def _validate_dense_order_sequence(actual_orders: set[int], expected_owner: str) -> None:
    expected_orders = set(range(1, len(actual_orders) + 1))
    if actual_orders != expected_orders:
        raise DatasetValidationError(
            f"{expected_owner} must be densely ordered from 1..n; got {sorted(actual_orders)}."
        )
