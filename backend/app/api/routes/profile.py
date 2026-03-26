from datetime import date

from fastapi import APIRouter, Query

from app.services.profile_service import (
    get_current_profile_overview,
    get_current_profile_progress_highlights,
    get_current_profile_timeline,
)

router = APIRouter(prefix="/profile")


@router.get("/current/overview")
def current_profile_overview() -> dict[str, object]:
    return get_current_profile_overview()


@router.get("/current/timeline")
def current_profile_timeline(
    limit: int = Query(30, ge=1, le=200),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_workouts: bool = Query(default=True),
    include_measurements: bool = Query(default=True),
) -> dict[str, object]:
    return get_current_profile_timeline(
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        include_workouts=include_workouts,
        include_measurements=include_measurements,
    )


@router.get("/current/progress-highlights")
def current_profile_progress_highlights() -> dict[str, object]:
    return get_current_profile_progress_highlights()
