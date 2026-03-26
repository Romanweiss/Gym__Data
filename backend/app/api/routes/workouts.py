from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.services.workout_service import list_workouts

router = APIRouter(prefix="/workouts")
settings = get_settings()


@router.get("/")
def workouts(
    limit: int = Query(settings.default_page_size, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source_quality: str | None = Query(default=None),
) -> dict[str, object]:
    return list_workouts(limit=limit, offset=offset, source_quality=source_quality)

