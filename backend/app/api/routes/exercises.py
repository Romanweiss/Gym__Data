from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.services.exercise_service import list_exercises

router = APIRouter(prefix="/exercises")
settings = get_settings()


@router.get("/")
def exercises(
    limit: int = Query(settings.default_page_size, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str | None = Query(default=None),
) -> dict[str, object]:
    return list_exercises(limit=limit, offset=offset, category=category)

