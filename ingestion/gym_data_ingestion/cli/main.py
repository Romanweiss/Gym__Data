import argparse
import json
from uuid import uuid4

from gym_data_ingestion.loaders.clickhouse import load_marts, load_measurement_marts
from gym_data_ingestion.loaders.postgres import (
    ensure_stage_1_2_schema,
    finish_run,
    load_measurement_dataset,
    load_workout_dataset,
    start_run,
)
from gym_data_ingestion.measurement_models import (
    MeasurementFlattenedData,
    build_flattened_measurement_dataset,
)
from gym_data_ingestion.measurement_reconciliation import (
    build_measurement_source_snapshot,
    load_measurement_flat_snapshot,
    load_measurement_raw_snapshot,
    reconcile_measurement_layers,
)
from gym_data_ingestion.models import (
    FlattenedData,
    SourceDocument,
    build_flattened_dataset,
    read_source_documents,
)
from gym_data_ingestion.reconciliation import (
    build_source_snapshot,
    load_flat_snapshot,
    load_raw_snapshot,
    reconcile_layers,
)
from gym_data_ingestion.settings import get_settings
from gym_data_ingestion.validation.schema import validate_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Gym__Data ingestion entrypoint")
    parser.add_argument(
        "command",
        choices=[
            "load-all",
            "load-workouts",
            "load-measurements",
            "reconcile",
            "reconcile-workouts",
            "reconcile-measurements",
        ],
    )
    args = parser.parse_args()

    if args.command == "load-all":
        run_load_all()
    elif args.command == "load-workouts":
        run_load_workouts()
    elif args.command == "load-measurements":
        run_load_measurements()
    elif args.command == "reconcile":
        run_reconciliation()
    elif args.command == "reconcile-workouts":
        run_workout_reconciliation()
    elif args.command == "reconcile-measurements":
        run_measurement_reconciliation()


def run_load_all() -> None:
    settings = get_settings()
    ensure_stage_1_2_schema(settings.postgres_dsn)
    workout_documents, workout_dataset = _build_workout_source_dataset()
    measurement_documents, measurement_dataset = _build_measurement_source_dataset()

    run_id = uuid4()
    start_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        source_file_count=len(workout_documents) + len(measurement_documents),
        details={
            "domains": {
                "workouts": {
                    "source_root": str(settings.workout_source_dir),
                    "schema_path": str(settings.workout_schema_path),
                    "workout_file_count": len(workout_documents),
                },
                "measurements": {
                    "source_root": str(settings.measurement_source_dir),
                    "schema_path": str(settings.measurement_schema_path),
                    "measurement_file_count": len(measurement_documents),
                },
            }
        },
    )

    try:
        workout_postgres_counts = load_workout_dataset(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            dataset=workout_dataset,
        )
        measurement_postgres_counts = load_measurement_dataset(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            dataset=measurement_dataset,
        )
        workout_clickhouse_counts = load_marts(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            dataset=workout_dataset,
        )
        measurement_clickhouse_counts = load_measurement_marts(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            workout_dataset=workout_dataset,
            measurement_dataset=measurement_dataset,
            cadence_days=settings.measurement_recommendation_cadence_days,
            default_subject_profile_id=settings.default_subject_profile_id,
        )
    except Exception as exc:
        finish_run(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            status="failed",
            details={"error": str(exc)},
        )
        raise

    finish_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        status="succeeded",
        details={
            "postgres_counts": {
                "workouts": workout_postgres_counts,
                "measurements": measurement_postgres_counts,
            },
            "clickhouse_counts": {
                "workouts": workout_clickhouse_counts,
                "measurements": measurement_clickhouse_counts,
            },
        },
    )

    print(
        json.dumps(
            {
                "run_id": str(run_id),
                "postgres_counts": {
                    "workouts": workout_postgres_counts,
                    "measurements": measurement_postgres_counts,
                },
                "clickhouse_counts": {
                    "workouts": workout_clickhouse_counts,
                    "measurements": measurement_clickhouse_counts,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_load_workouts() -> None:
    settings = get_settings()
    ensure_stage_1_2_schema(settings.postgres_dsn)
    workout_documents, workout_dataset = _build_workout_source_dataset()
    run_id = uuid4()
    start_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        source_file_count=len(workout_documents),
        details={
            "domain": "workouts",
            "source_root": str(settings.workout_source_dir),
            "schema_path": str(settings.workout_schema_path),
        },
    )

    try:
        postgres_counts = load_workout_dataset(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            dataset=workout_dataset,
        )
        clickhouse_counts = load_marts(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            dataset=workout_dataset,
        )
    except Exception as exc:
        finish_run(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            status="failed",
            details={"error": str(exc)},
        )
        raise

    finish_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        status="succeeded",
        details={"postgres_counts": postgres_counts, "clickhouse_counts": clickhouse_counts},
    )
    print(
        json.dumps(
            {
                "run_id": str(run_id),
                "postgres_counts": postgres_counts,
                "clickhouse_counts": clickhouse_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_load_measurements() -> None:
    settings = get_settings()
    ensure_stage_1_2_schema(settings.postgres_dsn)
    _, workout_dataset = _build_workout_source_dataset()
    measurement_documents, measurement_dataset = _build_measurement_source_dataset()
    run_id = uuid4()
    start_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        source_file_count=len(measurement_documents),
        details={
            "domain": "measurements",
            "source_root": str(settings.measurement_source_dir),
            "schema_path": str(settings.measurement_schema_path),
        },
    )

    try:
        postgres_counts = load_measurement_dataset(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            dataset=measurement_dataset,
        )
        clickhouse_counts = load_measurement_marts(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            workout_dataset=workout_dataset,
            measurement_dataset=measurement_dataset,
            cadence_days=settings.measurement_recommendation_cadence_days,
            default_subject_profile_id=settings.default_subject_profile_id,
        )
    except Exception as exc:
        finish_run(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            status="failed",
            details={"error": str(exc)},
        )
        raise

    finish_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        status="succeeded",
        details={"postgres_counts": postgres_counts, "clickhouse_counts": clickhouse_counts},
    )
    print(
        json.dumps(
            {
                "run_id": str(run_id),
                "postgres_counts": postgres_counts,
                "clickhouse_counts": clickhouse_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_reconciliation() -> None:
    workout_report = _build_workout_reconciliation_report()
    measurement_report = _build_measurement_reconciliation_report()
    print(workout_report.to_text())
    print()
    print(measurement_report.to_text())
    if workout_report.has_errors or measurement_report.has_errors:
        raise SystemExit(1)


def run_workout_reconciliation() -> None:
    workout_report = _build_workout_reconciliation_report()
    print(workout_report.to_text())
    if workout_report.has_errors:
        raise SystemExit(1)


def run_measurement_reconciliation() -> None:
    settings = get_settings()
    ensure_stage_1_2_schema(settings.postgres_dsn)
    measurement_report = _build_measurement_reconciliation_report()
    print(measurement_report.to_text())
    if measurement_report.has_errors:
        raise SystemExit(1)


def _build_workout_reconciliation_report():
    settings = get_settings()
    ensure_stage_1_2_schema(settings.postgres_dsn)
    _, workout_dataset = _build_workout_source_dataset()
    source_snapshot = build_source_snapshot(workout_dataset)
    flat_snapshot = load_flat_snapshot(settings.workout_flat_dir)
    raw_snapshot = load_raw_snapshot(settings.postgres_dsn)
    return reconcile_layers(source=source_snapshot, layers=[flat_snapshot, raw_snapshot])


def _build_measurement_reconciliation_report():
    settings = get_settings()
    _, measurement_dataset = _build_measurement_source_dataset()
    source_snapshot = build_measurement_source_snapshot(measurement_dataset)
    flat_snapshot = load_measurement_flat_snapshot(settings.measurement_flat_dir)
    raw_snapshot = load_measurement_raw_snapshot(settings.postgres_dsn)
    return reconcile_measurement_layers(
        source=source_snapshot,
        layers=[flat_snapshot, raw_snapshot],
    )


def _build_workout_source_dataset() -> tuple[list[SourceDocument], FlattenedData]:
    settings = get_settings()
    source_documents = read_source_documents(settings.workout_source_dir)
    for document in source_documents:
        validate_document(document.payload, settings.workout_schema_path)

    dataset = build_flattened_dataset(
        documents=source_documents,
        exercise_dictionary_path=settings.exercise_dictionary_path,
    )
    return source_documents, dataset


def _build_measurement_source_dataset() -> tuple[list[SourceDocument], MeasurementFlattenedData]:
    settings = get_settings()
    source_documents = read_source_documents(settings.measurement_source_dir)
    for document in source_documents:
        validate_document(document.payload, settings.measurement_schema_path)

    dataset = build_flattened_measurement_dataset(
        documents=source_documents,
        measurement_type_dictionary_path=settings.measurement_type_dictionary_path,
        default_subject_profile_id=settings.default_subject_profile_id,
    )
    return source_documents, dataset


if __name__ == "__main__":
    main()
