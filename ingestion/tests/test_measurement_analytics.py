from datetime import date
from pathlib import Path

from gym_data_ingestion.measurement_analytics import build_measurement_mart_payloads
from gym_data_ingestion.measurement_models import build_flattened_measurement_dataset
from gym_data_ingestion.models import build_flattened_dataset, read_source_documents

WORKOUT_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "workouts"
MEASUREMENT_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "measurements"


def test_measurement_marts_compute_latest_and_deltas() -> None:
    workout_dataset = build_flattened_dataset(
        read_source_documents(WORKOUT_FIXTURE_ROOT / "workouts"),
        WORKOUT_FIXTURE_ROOT / "flat" / "exercise_dictionary.jsonl",
    )
    measurement_dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_FIXTURE_ROOT / "measurements"),
        MEASUREMENT_FIXTURE_ROOT / "flat" / "measurement_type_dictionary.jsonl",
        "subject_default",
    )

    payloads = build_measurement_mart_payloads(
        workout_dataset=workout_dataset,
        measurement_dataset=measurement_dataset,
        cadence_days=21,
        default_subject_profile_id="subject_default",
        as_of_date=date(2026, 3, 26),
    )

    latest_body_weight = next(
        row
        for row in payloads["mart_measurement_latest"]["rows"]
        if row[1] == "body_weight"
    )
    latest_waist = next(
        row
        for row in payloads["mart_measurement_latest"]["rows"]
        if row[1] == "waist"
    )

    assert latest_body_weight[6] == "2026-03-01_morning"
    assert latest_body_weight[9] == 92.6
    assert latest_body_weight[13] == -0.6
    assert latest_waist[13] == -0.9


def test_measurement_overdue_logic_and_workout_bridge_are_grounded_in_existing_data() -> None:
    workout_dataset = build_flattened_dataset(
        read_source_documents(WORKOUT_FIXTURE_ROOT / "workouts"),
        WORKOUT_FIXTURE_ROOT / "flat" / "exercise_dictionary.jsonl",
    )
    measurement_dataset = build_flattened_measurement_dataset(
        read_source_documents(MEASUREMENT_FIXTURE_ROOT / "measurements"),
        MEASUREMENT_FIXTURE_ROOT / "flat" / "measurement_type_dictionary.jsonl",
        "subject_default",
    )

    payloads = build_measurement_mart_payloads(
        workout_dataset=workout_dataset,
        measurement_dataset=measurement_dataset,
        cadence_days=21,
        default_subject_profile_id="subject_default",
        as_of_date=date(2026, 3, 26),
    )

    overdue_row = payloads["mart_measurement_overdue"]["rows"][0]
    activity_row = next(
        row
        for row in payloads["mart_measurement_vs_workout_activity"]["rows"]
        if row[1] == "2026-03-01_morning"
    )

    assert overdue_row[0] == "subject_default"
    assert overdue_row[1] == 21
    assert overdue_row[2] == "2026-03-01_morning"
    assert overdue_row[6] > 0
    assert overdue_row[8] == 1
    assert "cadence threshold" in overdue_row[9]

    assert activity_row[5] > 0
    assert activity_row[6] == 0
    assert activity_row[8] == 0.0
    assert activity_row[9] > 0
