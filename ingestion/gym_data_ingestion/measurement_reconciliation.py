from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from psycopg import connect
from psycopg.rows import dict_row

from gym_data_ingestion.measurement_models import MeasurementFlattenedData

ENTITY_NAMES = (
    "subject_profiles",
    "body_measurement_sessions",
    "body_measurement_values",
    "measurement_type_dictionary",
)


@dataclass
class MeasurementLayerSnapshot:
    name: str
    subject_profiles: list[dict[str, Any]]
    body_measurement_sessions: list[dict[str, Any]]
    body_measurement_values: list[dict[str, Any]]
    measurement_type_dictionary: list[dict[str, Any]]


@dataclass
class MeasurementReconciliationIssue:
    severity: str
    layer: str
    entity: str
    code: str
    detail: str


@dataclass
class MeasurementReconciliationReport:
    source_counts: dict[str, int]
    layer_counts: dict[str, dict[str, int]]
    issues: list[MeasurementReconciliationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def to_text(self) -> str:
        lines = [
            "Gym__Data measurements reconciliation report",
            "",
            "Source counts:",
        ]
        for entity in ENTITY_NAMES:
            lines.append(f"  - {entity}: {self.source_counts[entity]}")

        for layer_name, counts in self.layer_counts.items():
            lines.extend(["", f"{layer_name} counts:"])
            for entity in ENTITY_NAMES:
                delta = counts[entity] - self.source_counts[entity]
                delta_text = f" (delta {delta:+d})" if delta else ""
                lines.append(f"  - {entity}: {counts[entity]}{delta_text}")

        lines.extend(["", f"Issues: {len(self.issues)}"])
        for issue in self.issues[:50]:
            lines.append(
                f"  - [{issue.severity}] {issue.layer}.{issue.entity}.{issue.code}: {issue.detail}"
            )
        if len(self.issues) > 50:
            lines.append(f"  - ... {len(self.issues) - 50} more issues omitted")

        lines.extend(["", f"Status: {'FAIL' if self.has_errors else 'PASS'}"])
        return "\n".join(lines)


def build_measurement_source_snapshot(
    dataset: MeasurementFlattenedData,
) -> MeasurementLayerSnapshot:
    return MeasurementLayerSnapshot(
        name="source",
        subject_profiles=[
            {
                "subject_profile_id": row["subject_profile_id"],
                "profile_kind": row["profile_kind"],
                "display_name": row["display_name"],
                "is_default": bool(row["is_default"]),
                "notes": row["notes"],
            }
            for row in dataset.subject_profiles
        ],
        body_measurement_sessions=[
            {
                "measurement_session_id": row["measurement_session_id"],
                "subject_profile_id": row["subject_profile_id"],
                "measured_at": _normalize_scalar(row["measured_at"]),
                "measured_date": _normalize_scalar(row["measured_date"]),
                "source_type": row["source_type"],
                "source_quality": row["source_quality"],
                "context_time_of_day": row["context_time_of_day"],
                "fasting_state": row["fasting_state"],
                "before_training": row["before_training"],
                "notes": row["notes"],
            }
            for row in dataset.body_measurement_sessions
        ],
        body_measurement_values=[
            {
                "measurement_session_id": row["measurement_session_id"],
                "measurement_value_id": row["measurement_value_id"],
                "measurement_type_canonical": row["measurement_type_canonical"],
                "measurement_type_raw": row["measurement_type_raw"],
                "value_numeric": _normalize_numeric(row["value_numeric"]),
                "unit": row["unit"],
                "side_or_scope": row["side_or_scope"],
                "raw_value": row["raw_value"],
                "parse_note": row["parse_note"],
                "notes": row["notes"],
                "order_in_session": int(row["order_in_session"]),
            }
            for row in dataset.body_measurement_values
        ],
        measurement_type_dictionary=[
            {
                "measurement_type_canonical": row["measurement_type_canonical"],
                "aliases": sorted(list(row["aliases"])),
                "default_unit": row["default_unit"],
                "category": row["category"],
                "sort_order": int(row["sort_order"]),
                "value_kind": row["value_kind"],
            }
            for row in dataset.measurement_type_dictionary
        ],
    )


def load_measurement_flat_snapshot(flat_dir: Path) -> MeasurementLayerSnapshot:
    subject_profiles = _read_jsonl(flat_dir / "subject_profiles.jsonl")
    sessions = _read_jsonl(flat_dir / "body_measurement_sessions.jsonl")
    values = _read_jsonl(flat_dir / "body_measurement_values.jsonl")
    dictionary_rows = _read_jsonl(flat_dir / "measurement_type_dictionary.jsonl")

    return MeasurementLayerSnapshot(
        name="flat",
        subject_profiles=[
            {
                "subject_profile_id": row["subject_profile_id"],
                "profile_kind": row["profile_kind"],
                "display_name": row["display_name"],
                "is_default": bool(row["is_default"]),
                "notes": row.get("notes"),
            }
            for row in subject_profiles
        ],
        body_measurement_sessions=[
            {
                "measurement_session_id": row["measurement_session_id"],
                "subject_profile_id": row["subject_profile_id"],
                "measured_at": str(row["measured_at"]),
                "measured_date": str(row["measured_date"]),
                "source_type": row.get("source_type"),
                "source_quality": row["source_quality"],
                "context_time_of_day": row["context_time_of_day"],
                "fasting_state": row.get("fasting_state"),
                "before_training": row.get("before_training"),
                "notes": row.get("notes"),
            }
            for row in sessions
        ],
        body_measurement_values=[
            {
                "measurement_session_id": row["measurement_session_id"],
                "measurement_value_id": row["measurement_value_id"],
                "measurement_type_canonical": row["measurement_type_canonical"],
                "measurement_type_raw": row["measurement_type_raw"],
                "value_numeric": _normalize_numeric(row["value_numeric"]),
                "unit": row["unit"],
                "side_or_scope": row.get("side_or_scope"),
                "raw_value": row.get("raw_value"),
                "parse_note": row.get("parse_note"),
                "notes": row.get("notes"),
                "order_in_session": int(row["order_in_session"]),
            }
            for row in values
        ],
        measurement_type_dictionary=[
            {
                "measurement_type_canonical": row["measurement_type_canonical"],
                "aliases": sorted([str(alias) for alias in row.get("aliases", [])]),
                "default_unit": row["default_unit"],
                "category": row["category"],
                "sort_order": int(row["sort_order"]),
                "value_kind": row["value_kind"],
            }
            for row in dictionary_rows
        ],
    )


def load_measurement_raw_snapshot(postgres_dsn: str) -> MeasurementLayerSnapshot:
    with connect(postgres_dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            subject_profiles = _fetch_rows(
                cursor,
                """
                SELECT
                    subject_profile_id,
                    profile_kind,
                    display_name,
                    is_default,
                    notes
                FROM raw.subject_profiles
                ORDER BY is_default DESC, subject_profile_id ASC
                """,
            )
            sessions = _fetch_rows(
                cursor,
                """
                SELECT
                    measurement_session_id,
                    subject_profile_id,
                    measured_at,
                    measured_date,
                    source_type,
                    source_quality,
                    context_time_of_day,
                    fasting_state,
                    before_training,
                    notes
                FROM raw.body_measurement_sessions
                ORDER BY measured_at, measurement_session_id
                """,
            )
            values = _fetch_rows(
                cursor,
                """
                SELECT
                    measurement_session_id,
                    measurement_value_id,
                    measurement_type_canonical,
                    measurement_type_raw,
                    value_numeric,
                    unit,
                    side_or_scope,
                    raw_value,
                    parse_note,
                    notes,
                    order_in_session
                FROM raw.body_measurement_values
                ORDER BY measurement_session_id, order_in_session
                """,
            )
            dictionary_rows = _fetch_rows(
                cursor,
                """
                SELECT
                    measurement_type_canonical,
                    aliases,
                    default_unit,
                    category,
                    sort_order,
                    value_kind
                FROM raw.measurement_type_dictionary
                ORDER BY sort_order, measurement_type_canonical
                """,
            )

    return MeasurementLayerSnapshot(
        name="raw",
        subject_profiles=[
            {
                "subject_profile_id": row["subject_profile_id"],
                "profile_kind": row["profile_kind"],
                "display_name": row["display_name"],
                "is_default": bool(row["is_default"]),
                "notes": row["notes"],
            }
            for row in subject_profiles
        ],
        body_measurement_sessions=[
            {
                "measurement_session_id": row["measurement_session_id"],
                "subject_profile_id": row["subject_profile_id"],
                "measured_at": _normalize_scalar(row["measured_at"]),
                "measured_date": _normalize_scalar(row["measured_date"]),
                "source_type": row["source_type"],
                "source_quality": row["source_quality"],
                "context_time_of_day": row["context_time_of_day"],
                "fasting_state": row["fasting_state"],
                "before_training": row["before_training"],
                "notes": row["notes"],
            }
            for row in sessions
        ],
        body_measurement_values=[
            {
                "measurement_session_id": row["measurement_session_id"],
                "measurement_value_id": row["measurement_value_id"],
                "measurement_type_canonical": row["measurement_type_canonical"],
                "measurement_type_raw": row["measurement_type_raw"],
                "value_numeric": _normalize_numeric(row["value_numeric"]),
                "unit": row["unit"],
                "side_or_scope": row["side_or_scope"],
                "raw_value": row["raw_value"],
                "parse_note": row["parse_note"],
                "notes": row["notes"],
                "order_in_session": int(row["order_in_session"]),
            }
            for row in values
        ],
        measurement_type_dictionary=[
            {
                "measurement_type_canonical": row["measurement_type_canonical"],
                "aliases": sorted(list(row["aliases"])),
                "default_unit": row["default_unit"],
                "category": row["category"],
                "sort_order": int(row["sort_order"]),
                "value_kind": row["value_kind"],
            }
            for row in dictionary_rows
        ],
    )


def reconcile_measurement_layers(
    source: MeasurementLayerSnapshot,
    layers: list[MeasurementLayerSnapshot],
) -> MeasurementReconciliationReport:
    report = MeasurementReconciliationReport(
        source_counts=_layer_counts(source),
        layer_counts={layer.name: _layer_counts(layer) for layer in layers},
    )
    source_maps = _build_entity_maps(source, report)

    for layer in layers:
        layer_maps = _build_entity_maps(layer, report)
        _compare_counts(report, source, layer)
        _compare_entity_rows(report, source_maps, layer_maps, layer.name)
        _check_references(report, layer)
        _check_ordering(report, layer)

    return report


def _compare_counts(
    report: MeasurementReconciliationReport,
    source: MeasurementLayerSnapshot,
    layer: MeasurementLayerSnapshot,
) -> None:
    source_counts = _layer_counts(source)
    layer_counts = _layer_counts(layer)
    for entity in ENTITY_NAMES:
        if source_counts[entity] != layer_counts[entity]:
            report.issues.append(
                MeasurementReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity=entity,
                    code="count_mismatch",
                    detail=f"source={source_counts[entity]} layer={layer_counts[entity]}",
                )
            )


def _compare_entity_rows(
    report: MeasurementReconciliationReport,
    source_maps: dict[str, dict[tuple[Any, ...], dict[str, Any]]],
    layer_maps: dict[str, dict[tuple[Any, ...], dict[str, Any]]],
    layer_name: str,
) -> None:
    for entity in ENTITY_NAMES:
        source_rows = source_maps[entity]
        layer_rows = layer_maps[entity]
        missing_keys = sorted(set(source_rows) - set(layer_rows))
        extra_keys = sorted(set(layer_rows) - set(source_rows))
        shared_keys = sorted(set(source_rows) & set(layer_rows))

        for key in missing_keys:
            report.issues.append(
                MeasurementReconciliationIssue(
                    severity="error",
                    layer=layer_name,
                    entity=entity,
                    code="missing_row",
                    detail=f"missing key {key}",
                )
            )
        for key in extra_keys:
            report.issues.append(
                MeasurementReconciliationIssue(
                    severity="error",
                    layer=layer_name,
                    entity=entity,
                    code="orphan_row",
                    detail=f"unexpected key {key}",
                )
            )
        for key in shared_keys:
            if source_rows[key] != layer_rows[key]:
                report.issues.append(
                    MeasurementReconciliationIssue(
                        severity="error",
                        layer=layer_name,
                        entity=entity,
                        code="row_mismatch",
                        detail=f"key {key}: source={source_rows[key]} layer={layer_rows[key]}",
                    )
                )


def _check_references(
    report: MeasurementReconciliationReport,
    layer: MeasurementLayerSnapshot,
) -> None:
    subject_profile_ids = {row["subject_profile_id"] for row in layer.subject_profiles}
    session_ids = {row["measurement_session_id"] for row in layer.body_measurement_sessions}

    for row in layer.body_measurement_sessions:
        if row["subject_profile_id"] not in subject_profile_ids:
            report.issues.append(
                MeasurementReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="body_measurement_sessions",
                    code="orphan_subject_profile_id",
                    detail=(
                        f"{row['measurement_session_id']} references missing subject_profile_id "
                        f"{row['subject_profile_id']}"
                    ),
                )
            )

    for row in layer.body_measurement_values:
        if row["measurement_session_id"] not in session_ids:
            report.issues.append(
                MeasurementReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="body_measurement_values",
                    code="orphan_measurement_session_id",
                    detail=(
                        f"{row['measurement_value_id']} references missing measurement_session_id "
                        f"{row['measurement_session_id']}"
                    ),
                )
            )


def _check_ordering(
    report: MeasurementReconciliationReport,
    layer: MeasurementLayerSnapshot,
) -> None:
    for measurement_session_id, rows in _group_by(
        layer.body_measurement_values,
        "measurement_session_id",
    ).items():
        orders = sorted(int(row["order_in_session"]) for row in rows)
        if orders != list(range(1, len(rows) + 1)):
            report.issues.append(
                MeasurementReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="body_measurement_values",
                    code="broken_order_in_session",
                    detail=(
                        f"measurement session {measurement_session_id} has order_in_session values {orders}"
                    ),
                )
            )


def _layer_counts(layer: MeasurementLayerSnapshot) -> dict[str, int]:
    return {
        "subject_profiles": len(layer.subject_profiles),
        "body_measurement_sessions": len(layer.body_measurement_sessions),
        "body_measurement_values": len(layer.body_measurement_values),
        "measurement_type_dictionary": len(layer.measurement_type_dictionary),
    }


def _build_entity_maps(
    layer: MeasurementLayerSnapshot,
    report: MeasurementReconciliationReport,
) -> dict[str, dict[tuple[Any, ...], dict[str, Any]]]:
    return {
        "subject_profiles": _build_map(
            layer.subject_profiles,
            ("subject_profile_id",),
            layer.name,
            "subject_profiles",
            report,
        ),
        "body_measurement_sessions": _build_map(
            layer.body_measurement_sessions,
            ("measurement_session_id",),
            layer.name,
            "body_measurement_sessions",
            report,
        ),
        "body_measurement_values": _build_map(
            layer.body_measurement_values,
            ("measurement_session_id", "order_in_session"),
            layer.name,
            "body_measurement_values",
            report,
        ),
        "measurement_type_dictionary": _build_map(
            layer.measurement_type_dictionary,
            ("measurement_type_canonical",),
            layer.name,
            "measurement_type_dictionary",
            report,
        ),
    }


def _build_map(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    layer_name: str,
    entity: str,
    report: MeasurementReconciliationReport,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    row_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    seen_duplicates: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in row_map:
            seen_duplicates.add(key)
        row_map[key] = row

    for key in sorted(seen_duplicates):
        report.issues.append(
            MeasurementReconciliationIssue(
                severity="error",
                layer=layer_name,
                entity=entity,
                code="duplicate_logical_row",
                detail=f"duplicate key {key}",
            )
        )

    return row_map


def _group_by(rows: Iterable[dict[str, Any]], key_field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key_field]), []).append(row)
    return grouped


def _fetch_rows(cursor: Any, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    return list(cursor.fetchall())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _normalize_numeric(value)
    if isinstance(value, float):
        return _normalize_numeric(value)
    if isinstance(value, list):
        return sorted([_normalize_scalar(item) for item in value])
    if isinstance(value, dict):
        return {key: _normalize_scalar(value[key]) for key in sorted(value)}
    return value


def _normalize_numeric(value: Any) -> str:
    decimal_value = Decimal(str(value))
    rendered = format(decimal_value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered
