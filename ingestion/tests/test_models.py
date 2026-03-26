import hashlib
import json
from pathlib import Path

from gym_data_ingestion.models import SourceDocument, build_flattened_dataset, read_source_documents

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "workouts"
WORKOUT_SOURCE_DIR = FIXTURE_ROOT / "workouts"
EXERCISE_DICTIONARY_PATH = FIXTURE_ROOT / "flat" / "exercise_dictionary.jsonl"


def test_build_flattened_dataset_happy_path_for_full_real_dataset() -> None:
    documents = read_source_documents(WORKOUT_SOURCE_DIR)
    dataset = build_flattened_dataset(documents, EXERCISE_DICTIONARY_PATH)

    assert len(dataset.workouts) == 43
    assert len(dataset.exercise_instances) == 165
    assert len(dataset.sets) == 241
    assert len(dataset.cardio_segments) == 45
    assert len(dataset.recovery_events) == 61


def test_incomplete_notation_contract_is_preserved() -> None:
    dataset = build_flattened_dataset(
        _documents("2026-03-08.json"),
        EXERCISE_DICTIONARY_PATH,
    )

    incomplete_set = next(
        row
        for row in dataset.sets
        if row["raw_value"] == "125х"
    )

    assert incomplete_set["reps"] == 1
    assert incomplete_set["parse_note"] == "reps_missing_defaulted_to_1"


def test_bodyweight_sets_keep_zero_weight() -> None:
    dataset = build_flattened_dataset(
        _documents("2026-03-05.json"),
        EXERCISE_DICTIONARY_PATH,
    )

    bodyweight_exercise_ids = {
        row["exercise_instance_id"]
        for row in dataset.exercise_instances
        if row["bodyweight"]
    }
    bodyweight_sets = [
        row for row in dataset.sets if row["exercise_instance_id"] in bodyweight_exercise_ids
    ]

    assert bodyweight_sets
    assert all(row["weight_kg"] == 0 for row in bodyweight_sets)


def test_source_quality_handling_preserves_partial_raw_mix() -> None:
    dataset = build_flattened_dataset(
        _documents("2026-03-23.json"),
        EXERCISE_DICTIONARY_PATH,
    )

    assert dataset.workouts[0]["source_quality"] == "partial_raw"
    exercise_qualities = {row["source_quality"] for row in dataset.exercise_instances}
    assert exercise_qualities == {"raw_detailed", "summary_only"}


def test_exercise_instance_ids_follow_stable_sequence_order() -> None:
    dataset = build_flattened_dataset(
        _documents("2026-03-07.json"),
        EXERCISE_DICTIONARY_PATH,
    )

    ids = [row["exercise_instance_id"] for row in dataset.exercise_instances]
    orders = [str(row["exercise_order"]) for row in dataset.exercise_instances]

    assert ids == [
        "2026-03-07_ex_01",
        "2026-03-07_ex_02",
        "2026-03-07_ex_03",
        "2026-03-07_ex_04",
        "2026-03-07_ex_05",
        "2026-03-07_ex_06",
        "2026-03-07_ex_07",
        "2026-03-07_ex_08",
        "2026-03-07_ex_09",
        "2026-03-07_ex_10",
        "2026-03-07_ex_11",
    ]
    assert orders == ["3", "4", "5", "6", "7", "8", "9", "10", "10.1", "10.2", "11"]


def _documents(*file_names: str) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for file_name in file_names:
        file_path = WORKOUT_SOURCE_DIR / file_name
        raw_text = file_path.read_text(encoding="utf-8")
        documents.append(
            SourceDocument(
                file_path=file_path,
                relative_path=file_path.as_posix(),
                file_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                payload=json.loads(raw_text),
            )
        )
    return documents
