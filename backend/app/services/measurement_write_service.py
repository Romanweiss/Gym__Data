from __future__ import annotations

from datetime import date
from typing import Any

from app.api.schemas.measurements import MeasurementSessionUpsertRequest
from app.core.config import get_settings
from app.services.measurement_refresh_service import (
    MeasurementRefreshValidationError,
    MeasurementSessionConflictError,
    MeasurementSessionNotFoundError,
    refresh_measurement_domain_from_payload,
)
from app.services.measurement_service import get_measurement_session_detail


class MeasurementWriteError(ValueError):
    """Raised when the write contract cannot be completed safely."""


def create_measurement_session(request: MeasurementSessionUpsertRequest) -> dict[str, Any]:
    settings = get_settings()
    resolved_measured_date = request.measured_date or request.measured_at.date()
    measurement_session_id = request.measurement_session_id or _generate_measurement_session_id(
        measured_date=resolved_measured_date,
        context_time_of_day=request.context_time_of_day,
    )
    payload = _build_source_payload(
        request=request,
        measurement_session_id=measurement_session_id,
        subject_profile_id=request.subject_profile_id or settings.default_subject_profile_id,
    )
    refresh = refresh_measurement_domain_from_payload(
        action="create",
        measurement_session_id=measurement_session_id,
        payload=payload,
    )
    detail = get_measurement_session_detail(measurement_session_id)
    if detail is None:
        raise MeasurementWriteError(
            f"Measurement session {measurement_session_id} was written but could not be read back."
        )
    return {
        "status": "created",
        "measurement_session": detail,
        "refresh": refresh,
    }


def update_measurement_session(
    measurement_session_id: str,
    request: MeasurementSessionUpsertRequest,
) -> dict[str, Any]:
    settings = get_settings()
    if request.measurement_session_id and request.measurement_session_id != measurement_session_id:
        raise MeasurementRefreshValidationError(
            "measurement_session_id in the request body must match the path parameter."
        )

    payload = _build_source_payload(
        request=request,
        measurement_session_id=measurement_session_id,
        subject_profile_id=request.subject_profile_id or settings.default_subject_profile_id,
    )
    refresh = refresh_measurement_domain_from_payload(
        action="update",
        measurement_session_id=measurement_session_id,
        payload=payload,
    )
    detail = get_measurement_session_detail(measurement_session_id)
    if detail is None:
        raise MeasurementWriteError(
            f"Measurement session {measurement_session_id} was updated but could not be read back."
        )
    return {
        "status": "updated",
        "measurement_session": detail,
        "refresh": refresh,
    }


def _build_source_payload(
    *,
    request: MeasurementSessionUpsertRequest,
    measurement_session_id: str,
    subject_profile_id: str,
) -> dict[str, Any]:
    measured_date = request.measured_date or request.measured_at.date()
    return {
        "measurement_session_id": measurement_session_id,
        "subject_profile_id": subject_profile_id,
        "measured_at": request.measured_at.isoformat(),
        "measured_date": measured_date.isoformat(),
        "source_type": request.source_type,
        "source_quality": request.source_quality,
        "context_time_of_day": request.context_time_of_day,
        "fasting_state": request.fasting_state,
        "before_training": request.before_training,
        "notes": request.notes,
        "measurements": [
            {
                "order_in_session": index,
                "measurement_type_raw": measurement.measurement_type.strip(),
                "value_numeric": measurement.value_numeric,
                "unit": measurement.unit,
                "side_or_scope": measurement.side_or_scope,
                "raw_value": measurement.raw_value,
                "notes": measurement.notes,
            }
            for index, measurement in enumerate(request.measurements, start=1)
        ],
    }


def _generate_measurement_session_id(
    *,
    measured_date: date,
    context_time_of_day: str,
) -> str:
    settings = get_settings()
    base_id = f"{measured_date.isoformat()}_{context_time_of_day}"
    candidate_id = base_id
    suffix = 2

    while (settings.measurement_source_dir / f"{candidate_id}.json").exists():
        candidate_id = f"{base_id}_{suffix:02d}"
        suffix += 1

    return candidate_id


__all__ = [
    "MeasurementRefreshValidationError",
    "MeasurementSessionConflictError",
    "MeasurementSessionNotFoundError",
    "create_measurement_session",
    "update_measurement_session",
]
