from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.services.measurement_service import (
    get_latest_measurements,
    get_measurement_overdue,
    get_measurement_progress,
    get_measurement_session_detail,
    list_measurement_sessions,
)

router = APIRouter(prefix="/measurements")
settings = get_settings()


@router.get("/")
def measurements(
    limit: int = Query(settings.default_page_size, ge=1, le=200),
    offset: int = Query(0, ge=0),
    measurement_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    subject_profile_id: str | None = Query(default=None),
) -> dict[str, object]:
    return list_measurement_sessions(
        limit=limit,
        offset=offset,
        measurement_type=measurement_type,
        date_from=date_from,
        date_to=date_to,
        subject_profile_id=subject_profile_id,
    )


@router.get("/latest")
def latest_measurements(
    subject_profile_id: str | None = Query(default=None),
) -> dict[str, object]:
    return get_latest_measurements(subject_profile_id=subject_profile_id)


@router.get("/progress")
def measurement_progress(
    subject_profile_id: str | None = Query(default=None),
    measurement_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, object]:
    return get_measurement_progress(
        subject_profile_id=subject_profile_id,
        measurement_type=measurement_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/overdue")
def measurement_overdue(
    subject_profile_id: str | None = Query(default=None),
) -> dict[str, object]:
    return get_measurement_overdue(subject_profile_id=subject_profile_id)


@router.get("/{measurement_session_id}")
def measurement_detail(measurement_session_id: str) -> dict[str, object]:
    detail = get_measurement_session_detail(measurement_session_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Measurement session {measurement_session_id} was not found.",
        )
    return detail
