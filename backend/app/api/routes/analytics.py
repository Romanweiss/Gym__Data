from fastapi import APIRouter, Query

from app.services.analytics_service import (
    get_cardio_analytics,
    get_recovery_analytics,
    get_weekly_training_load,
)

router = APIRouter(prefix="/analytics")


@router.get("/weekly-load")
def weekly_load(limit: int = Query(52, ge=1, le=260)) -> dict[str, object]:
    return get_weekly_training_load(limit=limit)


@router.get("/cardio")
def cardio(limit: int = Query(104, ge=1, le=520)) -> dict[str, object]:
    return get_cardio_analytics(limit=limit)


@router.get("/recovery")
def recovery(limit: int = Query(104, ge=1, le=520)) -> dict[str, object]:
    return get_recovery_analytics(limit=limit)
