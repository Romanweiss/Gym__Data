from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


class DatasetValidationError(ValueError):
    """Raised when source data violates the stage-1 data contract."""


Record = dict[str, Any]


@dataclass
class SourceDocument:
    file_path: Path
    relative_path: str
    file_sha256: str
    payload: Record


@dataclass
class FlattenedData:
    workouts: list[Record] = field(default_factory=list)
    exercise_instances: list[Record] = field(default_factory=list)
    sets: list[Record] = field(default_factory=list)
    cardio_segments: list[Record] = field(default_factory=list)
    recovery_events: list[Record] = field(default_factory=list)
    exercise_dictionary: list[Record] = field(default_factory=list)
    source_files: list[Record] = field(default_factory=list)


def read_source_documents(source_dir: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for file_path in sorted(source_dir.glob("*.json")):
        raw_text = file_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
        documents.append(
            SourceDocument(
                file_path=file_path,
                relative_path=file_path.as_posix(),
                file_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                payload=payload,
            )
        )
    if not documents:
        raise DatasetValidationError(f"No workout source files found in {source_dir}")
    return documents


def build_flattened_dataset(
    documents: list[SourceDocument],
    exercise_dictionary_path: Path,
) -> FlattenedData:
    dataset = FlattenedData()
    seen_workout_ids: set[str] = set()
    observed_dictionary: dict[str, Record] = {}
    observed_aliases: dict[str, set[str]] = {}

    for document in documents:
        workout = document.payload
        workout_id = str(workout["workout_id"])
        if workout_id in seen_workout_ids:
            raise DatasetValidationError(f"Duplicate workout_id detected: {workout_id}")
        seen_workout_ids.add(workout_id)

        source_quality = str(workout["source_quality"])
        if source_quality == "summary_only" and any(exercise.get("sets") for exercise in workout["exercises"]):
            raise DatasetValidationError(
                f"Workout {workout_id} is summary_only but contains set-level facts."
            )

        workout_date = date.fromisoformat(str(workout["date"]))
        dataset.workouts.append(
            {
                "workout_id": workout_id,
                "workout_date": workout_date,
                "session_sequence": int(workout.get("session_sequence") or 1),
                "title_raw": str(workout["title_raw"]),
                "split_raw": [str(item) for item in workout.get("split_raw", [])],
                "split_normalized": [str(item) for item in workout.get("split_normalized", [])],
                "source_type": workout.get("source_type"),
                "source_quality": source_quality,
                "source_text": workout.get("source_text"),
                "notes": workout.get("notes"),
                "raw_payload": workout,
            }
        )
        dataset.source_files.append(
            {
                "file_path": document.relative_path,
                "workout_id": workout_id,
                "source_quality": source_quality,
                "file_sha256": document.file_sha256,
            }
        )

        seen_exercise_orders: set[Decimal] = set()
        for exercise_index, exercise in enumerate(workout.get("exercises", []), start=1):
            exercise_order = Decimal(str(exercise["order"]))
            if exercise_order in seen_exercise_orders:
                raise DatasetValidationError(
                    f"Workout {workout_id} contains duplicate exercise order {exercise_order}."
                )
            seen_exercise_orders.add(exercise_order)

            exercise_instance_id = f"{workout_id}_ex_{exercise_index:02d}"
            exercise_name_canonical = str(exercise["exercise_name_canonical"])
            exercise_name_raw = str(exercise["exercise_name_raw"])
            category = str(exercise["category"])
            load_type = str(exercise["load_type"])
            bodyweight = bool(exercise["bodyweight"])
            exercise_quality = str(exercise.get("source_quality") or workout["source_quality"])

            observed_aliases.setdefault(exercise_name_canonical, set()).add(exercise_name_raw)
            if exercise_name_canonical in observed_dictionary:
                current = observed_dictionary[exercise_name_canonical]
                if current["category"] != category or current["load_type"] != load_type:
                    raise DatasetValidationError(
                        f"Canonical exercise {exercise_name_canonical} changed category/load_type."
                    )
            else:
                observed_dictionary[exercise_name_canonical] = {
                    "exercise_name_canonical": exercise_name_canonical,
                    "category": category,
                    "load_type": load_type,
                    "bodyweight_default": bodyweight,
                    "primary_muscles": [],
                    "source_payload": {
                        "source": "derived_from_workouts_json",
                        "exercise_name_raw_examples": [exercise_name_raw],
                    },
                }

            dataset.exercise_instances.append(
                {
                    "exercise_instance_id": exercise_instance_id,
                    "workout_id": workout_id,
                    "exercise_order": exercise_order,
                    "exercise_name_raw": exercise_name_raw,
                    "exercise_name_canonical": exercise_name_canonical,
                    "category": category,
                    "load_type": load_type,
                    "bodyweight": bodyweight,
                    "attributes": exercise.get("attributes") or {},
                    "raw_sets_text": exercise.get("raw_sets_text"),
                    "notes": exercise.get("notes"),
                    "source_quality": exercise_quality,
                    "raw_payload": exercise,
                }
            )

            seen_set_orders: set[int] = set()
            for set_row in exercise.get("sets", []):
                set_order = int(set_row["set_order"])
                if set_order in seen_set_orders:
                    raise DatasetValidationError(
                        f"Exercise {exercise_instance_id} contains duplicate set_order {set_order}."
                    )
                seen_set_orders.add(set_order)

                weight_kg = float(set_row["weight_kg"])
                reps = int(set_row["reps"])
                parse_note = set_row.get("parse_note")

                if bodyweight and weight_kg != 0:
                    raise DatasetValidationError(
                        f"Bodyweight exercise {exercise_instance_id} must keep weight_kg=0."
                    )
                if parse_note == "reps_missing_defaulted_to_1" and reps != 1:
                    raise DatasetValidationError(
                        f"Exercise {exercise_instance_id} set {set_order} lost reps default contract."
                    )

                dataset.sets.append(
                    {
                        "exercise_instance_id": exercise_instance_id,
                        "workout_id": workout_id,
                        "set_order": set_order,
                        "weight_kg": weight_kg,
                        "reps": reps,
                        "raw_value": set_row.get("raw_value"),
                        "parse_note": parse_note,
                        "raw_payload": set_row,
                    }
                )

        seen_cardio_orders: set[int] = set()
        for cardio in workout.get("cardio_segments", []):
            segment_order = int(cardio["order"])
            if segment_order in seen_cardio_orders:
                raise DatasetValidationError(
                    f"Workout {workout_id} contains duplicate cardio order {segment_order}."
                )
            seen_cardio_orders.add(segment_order)
            dataset.cardio_segments.append(
                {
                    "workout_id": workout_id,
                    "segment_order": segment_order,
                    "machine": str(cardio["machine"]),
                    "direction": cardio.get("direction"),
                    "duration_min": cardio.get("duration_min"),
                    "notes": cardio.get("notes"),
                    "raw_payload": cardio,
                }
            )

        seen_recovery_orders: set[int] = set()
        for recovery in workout.get("recovery_events", []):
            event_order = int(recovery["order"])
            if event_order in seen_recovery_orders:
                raise DatasetValidationError(
                    f"Workout {workout_id} contains duplicate recovery order {event_order}."
                )
            seen_recovery_orders.add(event_order)
            dataset.recovery_events.append(
                {
                    "workout_id": workout_id,
                    "event_order": event_order,
                    "event_type": str(recovery["event_type"]),
                    "duration_min": recovery.get("duration_min"),
                    "notes": recovery.get("notes"),
                    "raw_payload": recovery,
                }
            )

    curated_dictionary = _load_dictionary_file(exercise_dictionary_path)
    dataset.exercise_dictionary = _merge_dictionary_rows(
        curated_dictionary=curated_dictionary,
        observed_dictionary=observed_dictionary,
        observed_aliases=observed_aliases,
    )
    return dataset


def _load_dictionary_file(exercise_dictionary_path: Path) -> dict[str, Record]:
    if not exercise_dictionary_path.exists():
        return {}

    dictionary: dict[str, Record] = {}
    for line in exercise_dictionary_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        canonical = str(row["exercise_name_canonical"])
        if canonical in dictionary:
            raise DatasetValidationError(f"Duplicate exercise dictionary row: {canonical}")
        dictionary[canonical] = {
            "exercise_name_canonical": canonical,
            "aliases": [str(alias) for alias in row.get("aliases", [])],
            "category": str(row["category"]),
            "load_type": str(row["load_type"]),
            "bodyweight_default": bool(row.get("bodyweight_default", False)),
            "primary_muscles": [str(item) for item in row.get("primary_muscles", [])],
            "source_payload": row,
        }
    return dictionary


def _merge_dictionary_rows(
    curated_dictionary: dict[str, Record],
    observed_dictionary: dict[str, Record],
    observed_aliases: dict[str, set[str]],
) -> list[Record]:
    merged_rows: list[Record] = []
    all_canonicals = sorted(set(curated_dictionary) | set(observed_dictionary))

    for canonical in all_canonicals:
        if canonical in curated_dictionary:
            row = dict(curated_dictionary[canonical])
        else:
            row = dict(observed_dictionary[canonical])
            row["aliases"] = []

        alias_union = set(row.get("aliases", [])) | observed_aliases.get(canonical, set())
        row["aliases"] = sorted(alias_union)

        if canonical in observed_dictionary:
            observed = observed_dictionary[canonical]
            if row["category"] != observed["category"] or row["load_type"] != observed["load_type"]:
                raise DatasetValidationError(
                    f"Exercise dictionary conflicts with observed category/load_type for {canonical}."
                )
            if observed["bodyweight_default"] and not row["bodyweight_default"]:
                row["bodyweight_default"] = True

        merged_rows.append(row)

    return merged_rows
