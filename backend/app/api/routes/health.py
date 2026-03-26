from fastapi import APIRouter, Response

from app.services.health_service import get_health_report

router = APIRouter(prefix="/health")


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def health(response: Response) -> dict[str, object]:
    report = get_health_report()
    if report["status"] != "ok":
        response.status_code = 503
    return report

