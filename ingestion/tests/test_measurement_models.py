import json
from pathlib import Path

from gym_data_ingestion.measurement_models import (
    UNIT_DEFAULTED_PARSE_NOTE,
    build_flattened_measurement_dataset,
)
from gym_data_ingestion.models import read_source_documents
from gym_data_ingestion.validation.schema import validate_document

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "measurements"
MEASUREMENT_SOURCE_DIR = FIXTURE_ROOT / "measurements"
MEASUREMENT_FLAT_DIR = FIXTURE_ROOT / "flat"
MEASUREMENT_SCHEMA_PATH = FIXTURE_ROOT / "schema" / "measurement_session.schema.json"
MEASUREMENT_TYPE_DICTIONARY_PATH = MEASUREMENT_FLAT_DIR / "measurement_type_dictionary.jsonl"


def test_measurement_schema_validation_passes_for_real_fixture() -> None:
    payload = json.loads((MEASUREMENT_SOURCE_DIR / "2026-02-22_morning.json").read_text(encoding="utf-8"))
    validate_document(payload, MEASUREMENT_SCHEMA_PATH)


def test_build_flattened_measurement_dataset_happy_path() -> None:
    dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_SOURCE_DIR),
        MEASUREMENT_TYPE_DICTIONARY_PATH,
        "subject_default",
    )

    assert len(dataset.subject_profiles) == 1
    assert len(dataset.body_measurement_sessions) == 4
    assert len(dataset.body_measurement_values) == 40
    assert len(dataset.measurement_type_dictionary) == 10


def test_measurement_type_aliases_are_normalized_to_canonical_values() -> None:
    dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_SOURCE_DIR),
        MEASUREMENT_TYPE_DICTIONARY_PATH,
        "subject_default",
    )

    waist_row = next(
        row
        for row in dataset.body_measurement_values
        if row["measurement_type_raw"] == "обхват талии"
    )
    body_weight_row = next(
        row
        for row in dataset.body_measurement_values
        if row["measurement_type_raw"] == "масса тела"
    )

    assert waist_row["measurement_type_canonical"] == "waist"
    assert body_weight_row["measurement_type_canonical"] == "body_weight"


def test_missing_unit_defaults_from_measurement_type_dictionary() -> None:
    dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_SOURCE_DIR),
        MEASUREMENT_TYPE_DICTIONARY_PATH,
        "subject_default",
    )

    row = next(
        value
        for value in dataset.body_measurement_values
        if value["measurement_value_id"] == "2026-02-22_morning_mv_10"
    )

    assert row["unit"] == "kg"
    assert row["parse_note"] == UNIT_DEFAULTED_PARSE_NOTE
