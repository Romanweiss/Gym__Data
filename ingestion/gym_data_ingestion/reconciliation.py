from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from psycopg import connect
from psycopg.rows import dict_row

from gym_data_ingestion.models import FlattenedData

ENTITY_NAMES = (
    "workouts",
    "exercise_instances",
    "sets",
    "cardio_segments",
    "recovery_events",
)


@dataclass
class LayerSnapshot:
    name: str
    workouts: list[dict[str, Any]]
    exercise_instances: list[dict[str, Any]]
    sets: list[dict[str, Any]]
    cardio_segments: list[dict[str, Any]]
    recovery_events: list[dict[str, Any]]


@dataclass
class ReconciliationIssue:
    severity: str
    layer: str
    entity: str
    code: str
    detail: str


@dataclass
class ReconciliationReport:
    source_counts: dict[str, int]
    layer_counts: dict[str, dict[str, int]]
    issues: list[ReconciliationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def to_text(self) -> str:
        lines = [
            "Gym__Data reconciliation report",
            "",
            "Source counts:",
        ]
        for entity in ENTITY_NAMES:
            lines.append(f"  - {entity}: {self.source_counts[entity]}")

        for layer_name, counts in self.layer_counts.items():
            lines.extend(
                [
                    "",
                    f"{layer_name} counts:",
                ]
            )
            for entity in ENTITY_NAMES:
                delta = counts[entity] - self.source_counts[entity]
                delta_text = f" (delta {delta:+d})" if delta else ""
                lines.append(f"  - {entity}: {counts[entity]}{delta_text}")

        lines.extend(
            [
                "",
                f"Issues: {len(self.issues)}",
            ]
        )
        for issue in self.issues[:50]:
            lines.append(
                f"  - [{issue.severity}] {issue.layer}.{issue.entity}.{issue.code}: {issue.detail}"
            )
        if len(self.issues) > 50:
            lines.append(f"  - ... {len(self.issues) - 50} more issues omitted")

        lines.extend(
            [
                "",
                f"Status: {'FAIL' if self.has_errors else 'PASS'}",
            ]
        )
        return "\n".join(lines)


def build_source_snapshot(dataset: FlattenedData) -> LayerSnapshot:
    return LayerSnapshot(
        name="source",
        workouts=[
            {
                "workout_id": row["workout_id"],
                "date": _normalize_scalar(row["workout_date"]),
                "session_sequence": int(row["session_sequence"]),
                "title_raw": row["title_raw"],
                "split_raw": _normalize_list(row["split_raw"]),
                "split_normalized": _normalize_list(row["split_normalized"]),
                "source_quality": row["source_quality"],
                "notes": row["notes"],
            }
            for row in dataset.workouts
        ],
        exercise_instances=[
            {
                "exercise_instance_id": row["exercise_instance_id"],
                "workout_id": row["workout_id"],
                "display_order": _parse_display_order(row["exercise_instance_id"]),
                "order": _normalize_numeric(row["exercise_order"]),
                "exercise_name_raw": row["exercise_name_raw"],
                "exercise_name_canonical": row["exercise_name_canonical"],
                "category": row["category"],
                "load_type": row["load_type"],
                "bodyweight": bool(row["bodyweight"]),
                "attributes": _normalize_scalar(row["attributes"]),
                "raw_sets_text": row["raw_sets_text"],
                "notes": row["notes"],
                "source_quality": row["source_quality"],
            }
            for row in dataset.exercise_instances
        ],
        sets=[
            {
                "exercise_instance_id": row["exercise_instance_id"],
                "workout_id": row["workout_id"],
                "set_order": int(row["set_order"]),
                "weight_kg": _normalize_numeric(row["weight_kg"]),
                "reps": int(row["reps"]),
                "raw_value": row["raw_value"],
                "parse_note": row["parse_note"],
            }
            for row in dataset.sets
        ],
        cardio_segments=[
            {
                "workout_id": row["workout_id"],
                "order": int(row["segment_order"]),
                "machine": row["machine"],
                "direction": row["direction"],
                "duration_min": row["duration_min"],
                "notes": row["notes"],
            }
            for row in dataset.cardio_segments
        ],
        recovery_events=[
            {
                "workout_id": row["workout_id"],
                "order": int(row["event_order"]),
                "event_type": row["event_type"],
                "duration_min": row["duration_min"],
                "notes": row["notes"],
            }
            for row in dataset.recovery_events
        ],
    )


def load_flat_snapshot(flat_dir: Path) -> LayerSnapshot:
    workouts_rows = _read_jsonl(flat_dir / "workouts.jsonl")
    exercise_rows = _read_jsonl(flat_dir / "exercise_instances.jsonl")
    set_rows = _read_jsonl(flat_dir / "sets.jsonl")
    cardio_rows = _read_jsonl(flat_dir / "cardio_segments.jsonl")
    recovery_rows = _read_jsonl(flat_dir / "recovery_events.jsonl")

    return LayerSnapshot(
        name="flat",
        workouts=[
            {
                "workout_id": row["workout_id"],
                "date": str(row["date"]),
                "session_sequence": int(row.get("session_sequence") or 1),
                "title_raw": row["title_raw"],
                "split_raw": _normalize_list(row.get("split_raw", [])),
                "split_normalized": _normalize_list(row.get("split_normalized", [])),
                "source_quality": row["source_quality"],
                "notes": row.get("notes"),
            }
            for row in workouts_rows
        ],
        exercise_instances=[
            {
                "exercise_instance_id": row["exercise_instance_id"],
                "workout_id": row["workout_id"],
                "display_order": _parse_display_order(row["exercise_instance_id"]),
                "order": _normalize_numeric(row["order"]),
                "exercise_name_raw": row["exercise_name_raw"],
                "exercise_name_canonical": row["exercise_name_canonical"],
                "category": row["category"],
                "load_type": row["load_type"],
                "bodyweight": bool(row["bodyweight"]),
                "attributes": _normalize_scalar(row.get("attributes") or {}),
                "raw_sets_text": row.get("raw_sets_text"),
                "notes": row.get("notes"),
                "source_quality": row["source_quality"],
            }
            for row in exercise_rows
        ],
        sets=[
            {
                "exercise_instance_id": row["exercise_instance_id"],
                "workout_id": row["workout_id"],
                "set_order": int(row["set_order"]),
                "weight_kg": _normalize_numeric(row["weight_kg"]),
                "reps": int(row["reps"]),
                "raw_value": row.get("raw_value"),
                "parse_note": row.get("parse_note"),
            }
            for row in set_rows
        ],
        cardio_segments=[
            {
                "workout_id": row["workout_id"],
                "order": int(row["order"]),
                "machine": row["machine"],
                "direction": row.get("direction"),
                "duration_min": row.get("duration_min"),
                "notes": row.get("notes"),
            }
            for row in cardio_rows
        ],
        recovery_events=[
            {
                "workout_id": row["workout_id"],
                "order": int(row["order"]),
                "event_type": row["event_type"],
                "duration_min": row.get("duration_min"),
                "notes": row.get("notes"),
            }
            for row in recovery_rows
        ],
    )


def load_raw_snapshot(postgres_dsn: str) -> LayerSnapshot:
    with connect(postgres_dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            workouts = _fetch_rows(
                cursor,
                """
                SELECT
                    workout_id,
                    workout_date AS date,
                    session_sequence,
                    title_raw,
                    split_raw,
                    split_normalized,
                    source_quality,
                    notes
                FROM raw.workouts
                ORDER BY workout_date, workout_id
                """,
            )
            exercise_instances = _fetch_rows(
                cursor,
                """
                SELECT
                    exercise_instance_id,
                    workout_id,
                    exercise_order AS "order",
                    exercise_name_raw,
                    exercise_name_canonical,
                    category,
                    load_type,
                    bodyweight,
                    attributes,
                    raw_sets_text,
                    notes,
                    source_quality
                FROM raw.exercise_instances
                ORDER BY workout_id, exercise_order, exercise_instance_id
                """,
            )
            sets = _fetch_rows(
                cursor,
                """
                SELECT
                    exercise_instance_id,
                    workout_id,
                    set_order,
                    weight_kg,
                    reps,
                    raw_value,
                    parse_note
                FROM raw.sets
                ORDER BY workout_id, exercise_instance_id, set_order
                """,
            )
            cardio_segments = _fetch_rows(
                cursor,
                """
                SELECT
                    workout_id,
                    segment_order AS "order",
                    machine,
                    direction,
                    duration_min,
                    notes
                FROM raw.cardio_segments
                ORDER BY workout_id, segment_order
                """,
            )
            recovery_events = _fetch_rows(
                cursor,
                """
                SELECT
                    workout_id,
                    event_order AS "order",
                    event_type,
                    duration_min,
                    notes
                FROM raw.recovery_events
                ORDER BY workout_id, event_order
                """,
            )

    return LayerSnapshot(
        name="raw",
        workouts=[
            {
                "workout_id": row["workout_id"],
                "date": _normalize_scalar(row["date"]),
                "session_sequence": int(row["session_sequence"]),
                "title_raw": row["title_raw"],
                "split_raw": _normalize_list(row["split_raw"]),
                "split_normalized": _normalize_list(row["split_normalized"]),
                "source_quality": row["source_quality"],
                "notes": row["notes"],
            }
            for row in workouts
        ],
        exercise_instances=[
            {
                "exercise_instance_id": row["exercise_instance_id"],
                "workout_id": row["workout_id"],
                "display_order": _parse_display_order(row["exercise_instance_id"]),
                "order": _normalize_numeric(row["order"]),
                "exercise_name_raw": row["exercise_name_raw"],
                "exercise_name_canonical": row["exercise_name_canonical"],
                "category": row["category"],
                "load_type": row["load_type"],
                "bodyweight": bool(row["bodyweight"]),
                "attributes": _normalize_scalar(row["attributes"]),
                "raw_sets_text": row["raw_sets_text"],
                "notes": row["notes"],
                "source_quality": row["source_quality"],
            }
            for row in exercise_instances
        ],
        sets=[
            {
                "exercise_instance_id": row["exercise_instance_id"],
                "workout_id": row["workout_id"],
                "set_order": int(row["set_order"]),
                "weight_kg": _normalize_numeric(row["weight_kg"]),
                "reps": int(row["reps"]),
                "raw_value": row["raw_value"],
                "parse_note": row["parse_note"],
            }
            for row in sets
        ],
        cardio_segments=[
            {
                "workout_id": row["workout_id"],
                "order": int(row["order"]),
                "machine": row["machine"],
                "direction": row["direction"],
                "duration_min": row["duration_min"],
                "notes": row["notes"],
            }
            for row in cardio_segments
        ],
        recovery_events=[
            {
                "workout_id": row["workout_id"],
                "order": int(row["order"]),
                "event_type": row["event_type"],
                "duration_min": row["duration_min"],
                "notes": row["notes"],
            }
            for row in recovery_events
        ],
    )


def reconcile_layers(source: LayerSnapshot, layers: list[LayerSnapshot]) -> ReconciliationReport:
    report = ReconciliationReport(
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


def _compare_counts(report: ReconciliationReport, source: LayerSnapshot, layer: LayerSnapshot) -> None:
    source_counts = _layer_counts(source)
    layer_counts = _layer_counts(layer)
    for entity in ENTITY_NAMES:
        if source_counts[entity] != layer_counts[entity]:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity=entity,
                    code="count_mismatch",
                    detail=f"source={source_counts[entity]} layer={layer_counts[entity]}",
                )
            )


def _compare_entity_rows(
    report: ReconciliationReport,
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

        for key in missing_keys[:20]:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer_name,
                    entity=entity,
                    code="missing_row",
                    detail=f"missing key {key}",
                )
            )
        if len(missing_keys) > 20:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer_name,
                    entity=entity,
                    code="missing_row_truncated",
                    detail=f"{len(missing_keys) - 20} additional missing keys omitted",
                )
            )

        for key in extra_keys[:20]:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer_name,
                    entity=entity,
                    code="orphan_row",
                    detail=f"unexpected key {key}",
                )
            )
        if len(extra_keys) > 20:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer_name,
                    entity=entity,
                    code="orphan_row_truncated",
                    detail=f"{len(extra_keys) - 20} additional orphan keys omitted",
                )
            )

        for key in shared_keys:
            if source_rows[key] != layer_rows[key]:
                report.issues.append(
                    ReconciliationIssue(
                        severity="error",
                        layer=layer_name,
                        entity=entity,
                        code="row_mismatch",
                        detail=f"key {key}: source={source_rows[key]} layer={layer_rows[key]}",
                    )
                )


def _check_references(report: ReconciliationReport, layer: LayerSnapshot) -> None:
    workout_ids = {row["workout_id"] for row in layer.workouts}
    exercise_ids = {row["exercise_instance_id"] for row in layer.exercise_instances}
    exercise_to_workout = {
        row["exercise_instance_id"]: row["workout_id"] for row in layer.exercise_instances
    }

    for row in layer.exercise_instances:
        if row["workout_id"] not in workout_ids:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="exercise_instances",
                    code="orphan_workout_id",
                    detail=f"{row['exercise_instance_id']} references missing workout {row['workout_id']}",
                )
            )
        prefixed_workout = _workout_id_from_exercise_instance_id(row["exercise_instance_id"])
        if prefixed_workout != row["workout_id"]:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="exercise_instances",
                    code="exercise_instance_workout_mismatch",
                    detail=f"{row['exercise_instance_id']} points to workout_id={row['workout_id']}",
                )
            )

    for row in layer.sets:
        exercise_id = row["exercise_instance_id"]
        if exercise_id not in exercise_ids:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="sets",
                    code="orphan_exercise_instance_id",
                    detail=f"set row references missing exercise_instance_id {exercise_id}",
                )
            )
            continue
        expected_workout_id = exercise_to_workout[exercise_id]
        if row["workout_id"] != expected_workout_id:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="sets",
                    code="workout_id_mismatch",
                    detail=(
                        f"set row {exercise_id}/{row['set_order']} has workout_id={row['workout_id']} "
                        f"but exercise belongs to {expected_workout_id}"
                    ),
                )
            )

    for row in layer.cardio_segments:
        if row["workout_id"] not in workout_ids:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="cardio_segments",
                    code="orphan_workout_id",
                    detail=f"cardio segment references missing workout {row['workout_id']}",
                )
            )

    for row in layer.recovery_events:
        if row["workout_id"] not in workout_ids:
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="recovery_events",
                    code="orphan_workout_id",
                    detail=f"recovery event references missing workout {row['workout_id']}",
                )
            )


def _check_ordering(report: ReconciliationReport, layer: LayerSnapshot) -> None:
    for workout_id, rows in _group_by(layer.exercise_instances, "workout_id").items():
        display_orders = sorted(row["display_order"] for row in rows)
        if display_orders != list(range(1, len(rows) + 1)):
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="exercise_instances",
                    code="broken_display_order",
                    detail=f"workout {workout_id} has display orders {display_orders}",
                )
            )

        ordered_rows = sorted(rows, key=lambda row: row["display_order"])
        source_orders = [Decimal(str(row["order"])) for row in ordered_rows]
        if source_orders != sorted(source_orders):
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="exercise_instances",
                    code="broken_source_order",
                    detail=f"workout {workout_id} has non-monotonic source orders {source_orders}",
                )
            )

    for exercise_instance_id, rows in _group_by(layer.sets, "exercise_instance_id").items():
        set_orders = sorted(row["set_order"] for row in rows)
        if set_orders != list(range(1, len(rows) + 1)):
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="sets",
                    code="broken_set_order",
                    detail=f"exercise {exercise_instance_id} has set orders {set_orders}",
                )
            )

    for workout_id, rows in _group_by(layer.cardio_segments, "workout_id").items():
        orders = [int(row["order"]) for row in rows]
        if orders != sorted(orders):
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="cardio_segments",
                    code="broken_segment_order",
                    detail=f"workout {workout_id} has cardio orders {orders}",
                )
            )

    for workout_id, rows in _group_by(layer.recovery_events, "workout_id").items():
        orders = [int(row["order"]) for row in rows]
        if orders != sorted(orders):
            report.issues.append(
                ReconciliationIssue(
                    severity="error",
                    layer=layer.name,
                    entity="recovery_events",
                    code="broken_event_order",
                    detail=f"workout {workout_id} has recovery orders {orders}",
                )
            )


def _layer_counts(layer: LayerSnapshot) -> dict[str, int]:
    return {
        "workouts": len(layer.workouts),
        "exercise_instances": len(layer.exercise_instances),
        "sets": len(layer.sets),
        "cardio_segments": len(layer.cardio_segments),
        "recovery_events": len(layer.recovery_events),
    }


def _build_entity_maps(
    layer: LayerSnapshot,
    report: ReconciliationReport,
) -> dict[str, dict[tuple[Any, ...], dict[str, Any]]]:
    return {
        "workouts": _build_map(layer.workouts, ("workout_id",), layer.name, "workouts", report),
        "exercise_instances": _build_map(
            layer.exercise_instances,
            ("exercise_instance_id",),
            layer.name,
            "exercise_instances",
            report,
        ),
        "sets": _build_map(
            layer.sets,
            ("exercise_instance_id", "set_order"),
            layer.name,
            "sets",
            report,
        ),
        "cardio_segments": _build_map(
            layer.cardio_segments,
            ("workout_id", "order"),
            layer.name,
            "cardio_segments",
            report,
        ),
        "recovery_events": _build_map(
            layer.recovery_events,
            ("workout_id", "order"),
            layer.name,
            "recovery_events",
            report,
        ),
    }


def _build_map(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    layer_name: str,
    entity: str,
    report: ReconciliationReport,
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
            ReconciliationIssue(
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
    if not path.exists():
        raise FileNotFoundError(f"Flat file is missing: {path}")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _normalize_numeric(value)
    if isinstance(value, float):
        return _normalize_numeric(value)
    if isinstance(value, list):
        return _normalize_list(value)
    if isinstance(value, dict):
        return {key: _normalize_scalar(value[key]) for key in sorted(value)}
    return value


def _normalize_list(values: Iterable[Any]) -> list[Any]:
    return [_normalize_scalar(value) for value in values]


def _normalize_numeric(value: Any) -> str:
    decimal_value = Decimal(str(value))
    rendered = format(decimal_value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _parse_display_order(exercise_instance_id: str) -> int:
    match = re.search(r"_ex_(\d+)$", exercise_instance_id)
    if not match:
        raise ValueError(f"Unexpected exercise_instance_id format: {exercise_instance_id}")
    return int(match.group(1))


def _workout_id_from_exercise_instance_id(exercise_instance_id: str) -> str:
    return exercise_instance_id.rsplit("_ex_", 1)[0]
