from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.services.exercise_service import get_exercise_progress, list_exercises

router = APIRouter(prefix="/exercises")
settings = get_settings()


@router.get("/")
def exercises(
    limit: int = Query(settings.default_page_size, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str | None = Query(default=None),
) -> dict[str, object]:
    return list_exercises(limit=limit, offset=offset, category=category)


@router.get("/{exercise_name_canonical}/progress")
def exercise_progress(exercise_name_canonical: str) -> dict[str, object]:
    progress = get_exercise_progress(exercise_name_canonical)
    if progress is None:
        raise HTTPException(
            status_code=404,
            detail=f"Exercise {exercise_name_canonical} was not found.",
        )
    return progress

