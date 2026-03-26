import argparse
import json
from uuid import uuid4

from gym_data_ingestion.loaders.clickhouse import load_marts
from gym_data_ingestion.loaders.postgres import finish_run, load_dataset, start_run
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
    parser.add_argument("command", choices=["load-all", "reconcile"])
    args = parser.parse_args()

    if args.command == "load-all":
        run_load_all()
    if args.command == "reconcile":
        run_reconciliation()


def run_load_all() -> None:
    settings = get_settings()
    source_documents, dataset = _build_source_dataset()

    run_id = uuid4()
    start_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        source_file_count=len(source_documents),
        details={
            "source_root": str(settings.workout_source_dir),
            "schema_path": str(settings.workout_schema_path),
            "workout_file_count": len(dataset.workouts),
        },
    )

    try:
        postgres_counts = load_dataset(
            postgres_dsn=settings.postgres_dsn,
            run_id=run_id,
            dataset=dataset,
        )
        clickhouse_counts = load_marts(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            dataset=dataset,
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
            "postgres_counts": postgres_counts,
            "clickhouse_counts": clickhouse_counts,
        },
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
    settings = get_settings()
    _, dataset = _build_source_dataset()
    source_snapshot = build_source_snapshot(dataset)
    flat_snapshot = load_flat_snapshot(settings.workout_flat_dir)
    raw_snapshot = load_raw_snapshot(settings.postgres_dsn)

    report = reconcile_layers(
        source=source_snapshot,
        layers=[flat_snapshot, raw_snapshot],
    )
    print(report.to_text())
    if report.has_errors:
        raise SystemExit(1)


def _build_source_dataset() -> tuple[list[SourceDocument], FlattenedData]:
    settings = get_settings()
    source_documents = read_source_documents(settings.workout_source_dir)

    for document in source_documents:
        validate_document(document.payload, settings.workout_schema_path)

    dataset = build_flattened_dataset(
        documents=source_documents,
        exercise_dictionary_path=settings.exercise_dictionary_path,
    )
    return source_documents, dataset


if __name__ == "__main__":
    main()
