from datetime import datetime, timezone
from pathlib import Path

from gym_data_ingestion.measurement_models import build_flattened_measurement_dataset
from gym_data_ingestion.measurement_reconciliation import (
    _normalize_scalar,
    build_measurement_source_snapshot,
    load_measurement_flat_snapshot,
    reconcile_measurement_layers,
)
from gym_data_ingestion.models import read_source_documents

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "measurements"
MEASUREMENT_SOURCE_DIR = FIXTURE_ROOT / "measurements"
MEASUREMENT_FLAT_DIR = FIXTURE_ROOT / "flat"


def test_measurement_reconciliation_passes_against_flat_fixture() -> None:
    dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_SOURCE_DIR),
        MEASUREMENT_FLAT_DIR / "measurement_type_dictionary.jsonl",
        "subject_default",
    )

    report = reconcile_measurement_layers(
        build_measurement_source_snapshot(dataset),
        [load_measurement_flat_snapshot(MEASUREMENT_FLAT_DIR)],
    )

    assert not report.has_errors
    assert "Status: PASS" in report.to_text()


def test_measurement_reconciliation_detects_duplicate_logical_rows() -> None:
    dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_SOURCE_DIR),
        MEASUREMENT_FLAT_DIR / "measurement_type_dictionary.jsonl",
        "subject_default",
    )
    flat_snapshot = load_measurement_flat_snapshot(MEASUREMENT_FLAT_DIR)
    flat_snapshot.body_measurement_values.append(dict(flat_snapshot.body_measurement_values[0]))

    report = reconcile_measurement_layers(
        build_measurement_source_snapshot(dataset),
        [flat_snapshot],
    )

    assert report.has_errors
    assert any(issue.code == "duplicate_logical_row" for issue in report.issues)


def test_measurement_reconciliation_normalizes_utc_timestamps_to_stable_iso() -> None:
    rendered = _normalize_scalar(
        datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)
    )

    assert rendered == "2026-03-01T08:00:00"
