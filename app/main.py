"""FastAPI application entry point."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.api.routes import router
from app.core.config import settings
from app.core.security import RequestLimits, SecurityMiddleware
from app.models.schemas import TemplateLayout
from app.services.pdf_service import TemplateError, load_template


def create_app(
    template_path: Path | None = None, layout_path: Path | None = None,
    *, request_limits: RequestLimits | None = None, enable_bulk: bool = False,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        template = load_template(template_path or settings.template_path)
        try:
            with (layout_path or settings.layout_path).open(encoding="utf-8") as stream:
                layout = TemplateLayout.model_validate(json.load(stream))
        except (OSError, ValueError, ValidationError) as error:
            raise TemplateError("Template calibration configuration is invalid.") from error

        first_page = template.inspection["pages"][0]
        if (
            layout.template_sha256 != template.inspection["sha256"]
            or abs(layout.page_width - first_page["width"]) > 0.001
            or abs(layout.page_height - first_page["height"]) > 0.001
            or first_page["rotation"] != 0
        ):
            raise TemplateError("Template has changed and requires recalibration.")

        application.state.template = template
        application.state.layout = layout
        application.state.preview_png = template.preview_png()
        yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=False,
        lifespan=lifespan,
    )
    application.add_middleware(SecurityMiddleware, limits=request_limits or RequestLimits())

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {
                "loc": [
                    part if isinstance(part, int) or part in {"body", "name", "second_line", "city"}
                    else "unknown_field"
                    for part in item["loc"]
                ],
                "msg": item["msg"], "type": item["type"],
            }
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": details},
            headers={"Cache-Control": "no-store"},
        )

    application.include_router(router)
    if enable_bulk:
        from app.api.bulk_routes import router as bulk_router

        application.include_router(bulk_router)

    @application.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(settings.frontend_path / "index.html", media_type="text/html")

    application.mount(
        "/static/css", StaticFiles(directory=settings.frontend_path / "css"), name="css"
    )
    application.mount(
        "/static/js", StaticFiles(directory=settings.frontend_path / "js"), name="js"
    )
    return application


app = create_app()