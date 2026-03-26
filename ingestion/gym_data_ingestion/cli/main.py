import argparse
import json
from uuid import uuid4

from gym_data_ingestion.loaders.clickhouse import load_marts
from gym_data_ingestion.loaders.postgres import finish_run, load_dataset, start_run
from gym_data_ingestion.models import build_flattened_dataset, read_source_documents
from gym_data_ingestion.settings import get_settings
from gym_data_ingestion.validation.schema import validate_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Gym__Data ingestion entrypoint")
    parser.add_argument("command", choices=["load-all"])
    args = parser.parse_args()

    if args.command == "load-all":
        run_load_all()


def run_load_all() -> None:
    settings = get_settings()
    source_documents = read_source_documents(settings.workout_source_dir)

    for document in source_documents:
        validate_document(document.payload, settings.workout_schema_path)

    dataset = build_flattened_dataset(
        documents=source_documents,
        exercise_dictionary_path=settings.exercise_dictionary_path,
    )

    run_id = uuid4()
    start_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        source_file_count=len(source_documents),
        details={
            "source_root": str(settings.workout_source_dir),
            "schema_path": str(settings.workout_schema_path),
            "workout_file_count": len(source_documents),
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


if __name__ == "__main__":
    main()

