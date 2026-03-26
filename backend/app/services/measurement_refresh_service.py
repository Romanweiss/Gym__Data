from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from gym_data_ingestion.loaders.clickhouse import load_measurement_marts
from gym_data_ingestion.loaders.postgres import (
    ensure_stage_1_2_schema,
    finish_run,
    load_measurement_dataset,
    start_run,
)
from gym_data_ingestion.measurement_flat_files import write_measurement_flat_dataset
from gym_data_ingestion.measurement_models import build_flattened_measurement_dataset
from gym_data_ingestion.models import (
    DatasetValidationError,
    SourceDocument,
    build_flattened_dataset,
    read_source_documents,
)
from gym_data_ingestion.validation.schema import validate_document

from app.core.config import get_settings


class MeasurementRefreshValidationError(ValueError):
    """Raised when a proposed measurement write violates the data contract."""


class MeasurementSessionConflictError(MeasurementRefreshValidationError):
    """Raised when a created measurement session id already exists."""


class MeasurementSessionNotFoundError(MeasurementRefreshValidationError):
    """Raised when a patched measurement session does not exist."""


def refresh_measurement_domain_from_payload(
    *,
    action: Literal["create", "update"],
    measurement_session_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    source_dir = settings.measurement_source_dir
    source_dir.mkdir(parents=True, exist_ok=True)
    settings.measurement_flat_dir.mkdir(parents=True, exist_ok=True)

    source_documents = _read_source_documents_allow_empty(source_dir)
    documents_by_id = {
        str(document.payload["measurement_session_id"]): document
        for document in source_documents
    }

    if action == "create" and measurement_session_id in documents_by_id:
        raise MeasurementSessionConflictError(
            f"Measurement session {measurement_session_id} already exists."
        )
    if action == "update" and measurement_session_id not in documents_by_id:
        raise MeasurementSessionNotFoundError(
            f"Measurement session {measurement_session_id} was not found."
        )

    replacement_document = _build_source_document(
        source_dir / f"{measurement_session_id}.json",
        payload,
    )

    candidate_documents: list[SourceDocument] = []
    replaced = False
    for document in source_documents:
        if str(document.payload["measurement_session_id"]) == measurement_session_id:
            candidate_documents.append(replacement_document)
            replaced = True
        else:
            candidate_documents.append(document)

    if not replaced:
        candidate_documents.append(replacement_document)

    candidate_documents = sorted(candidate_documents, key=lambda document: document.file_path.name)
    for document in candidate_documents:
        validate_document(document.payload, settings.measurement_schema_path)

    try:
        measurement_dataset = build_flattened_measurement_dataset(
            documents=candidate_documents,
            measurement_type_dictionary_path=settings.measurement_type_dictionary_path,
            default_subject_profile_id=settings.default_subject_profile_id,
        )
    except DatasetValidationError as exc:
        raise MeasurementRefreshValidationError(str(exc)) from exc

    workout_documents = read_source_documents(settings.workout_source_dir)
    for document in workout_documents:
        validate_document(document.payload, settings.workout_schema_path)
    workout_dataset = build_flattened_dataset(
        documents=workout_documents,
        exercise_dictionary_path=settings.exercise_dictionary_path,
    )

    _write_source_payload(replacement_document.file_path, payload)
    write_measurement_flat_dataset(settings.measurement_flat_dir, measurement_dataset)

    run_id = uuid4()
    ensure_stage_1_2_schema(settings.postgres_dsn)
    start_run(
        postgres_dsn=settings.postgres_dsn,
        run_id=run_id,
        source_file_count=len(candidate_documents),
        details={
            "domain": "measurements",
            "trigger": "api_write",
            "action": action,
            "measurement_session_id": measurement_session_id,
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
        details={
            "trigger": "api_write",
            "action": action,
            "postgres_counts": postgres_counts,
            "clickhouse_counts": clickhouse_counts,
        },
    )

    return {
        "run_id": str(run_id),
        "source_file_count": len(candidate_documents),
        "postgres_counts": postgres_counts,
        "clickhouse_counts": clickhouse_counts,
    }


def _read_source_documents_allow_empty(source_dir: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for file_path in sorted(source_dir.glob("*.json")):
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


def _build_source_document(file_path: Path, payload: dict[str, Any]) -> SourceDocument:
    raw_text = _render_source_payload(payload)
    return SourceDocument(
        file_path=file_path,
        relative_path=file_path.as_posix(),
        file_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        payload=payload,
    )


def _write_source_payload(file_path: Path, payload: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(_render_source_payload(payload), encoding="utf-8")


def _render_source_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
