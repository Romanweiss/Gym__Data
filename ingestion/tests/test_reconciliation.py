from pathlib import Path

from gym_data_ingestion.models import build_flattened_dataset, read_source_documents
from gym_data_ingestion.reconciliation import build_source_snapshot, load_flat_snapshot, reconcile_layers

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "workouts"
WORKOUT_SOURCE_DIR = FIXTURE_ROOT / "workouts"
WORKOUT_FLAT_DIR = FIXTURE_ROOT / "flat"
EXERCISE_DICTIONARY_PATH = WORKOUT_FLAT_DIR / "exercise_dictionary.jsonl"


def test_reconciliation_passes_against_real_flat_export() -> None:
    dataset = build_flattened_dataset(
        read_source_documents(WORKOUT_SOURCE_DIR),
        EXERCISE_DICTIONARY_PATH,
    )
    source_snapshot = build_source_snapshot(dataset)
    flat_snapshot = load_flat_snapshot(WORKOUT_FLAT_DIR)

    report = reconcile_layers(source_snapshot, [flat_snapshot])

    assert not report.has_errors
    assert "Status: PASS" in report.to_text()


def test_reconciliation_detects_duplicate_logical_rows() -> None:
    dataset = build_flattened_dataset(
        read_source_documents(WORKOUT_SOURCE_DIR),
        EXERCISE_DICTIONARY_PATH,
    )
    source_snapshot = build_source_snapshot(dataset)
    flat_snapshot = load_flat_snapshot(WORKOUT_FLAT_DIR)
    flat_snapshot.sets.append(dict(flat_snapshot.sets[0]))

    report = reconcile_layers(source_snapshot, [flat_snapshot])

    assert report.has_errors
    assert any(issue.code == "duplicate_logical_row" for issue in report.issues)
