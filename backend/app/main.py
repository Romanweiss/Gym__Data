from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.responses import UTF8JSONResponse


def create_app() -> FastAPI:
    settings = get_settings()
    ui_dir = Path(__file__).resolve().parent / "ui"
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        default_response_class=UTF8JSONResponse,
    )
    application.include_router(api_router)
    if ui_dir.exists():
        @application.get("/ui", include_in_schema=False)
        @application.get("/ui/", include_in_schema=False)
        def workspace_ui() -> FileResponse:
            return FileResponse(ui_dir / "index.html")

        application.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")

        @application.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(url="/ui/")

    return application


app = create_app()
