from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.services.workout_service import get_workout_detail, get_workout_summary, list_workouts

router = APIRouter(prefix="/workouts")
settings = get_settings()


@router.get("/")
def workouts(
    limit: int = Query(settings.default_page_size, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source_quality: str | None = Query(default=None),
) -> dict[str, object]:
    return list_workouts(limit=limit, offset=offset, source_quality=source_quality)


@router.get("/{workout_id}")
def workout_detail(workout_id: str) -> dict[str, object]:
    detail = get_workout_detail(workout_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Workout {workout_id} was not found.")
    return detail


@router.get("/{workout_id}/summary")
def workout_summary(workout_id: str) -> dict[str, object]:
    summary = get_workout_summary(workout_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Workout {workout_id} summary was not found.")
    return summary
