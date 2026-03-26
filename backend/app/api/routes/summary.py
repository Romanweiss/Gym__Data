from fastapi import APIRouter

from app.services.summary_service import get_summary

router = APIRouter(prefix="/summary")


@router.get("/")
def summary() -> dict[str, object]:
    return get_summary()

