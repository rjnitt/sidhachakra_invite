"""Template inspection and single-invitation PDF download endpoints."""

from threading import Lock
from typing import Literal
from urllib.parse import quote

import pymupdf

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import RecipientRequest
from app.services.pdf_service import TemplateError, generate_invitation
from app.services.text_layout_service import LayoutError, RecipientText

router = APIRouter(prefix="/api")
generation_lock = Lock()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    template_loaded: bool


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Report validated template loading, not approval or generation readiness."""
    return HealthResponse(
        status="ok", template_loaded=request.app.state.template is not None
    )


@router.get("/template/preview")
def template_preview(request: Request) -> Response:
    return Response(
        content=request.app.state.preview_png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/template/layout")
def template_layout(request: Request) -> dict:
    return request.app.state.layout.public_configuration()


@router.get("/template/font", include_in_schema=False)
def template_font() -> FileResponse:
    """Expose only the approved bundled font, never an arbitrary asset path."""
    return FileResponse(settings.font_path, media_type="font/ttf")


@router.post(
    "/invitations/preview",
    response_class=Response,
    responses={
        200: {
            "description": "Personalized first-page PNG",
            "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}},
        },
        422: {"description": "Invalid recipient or unsafe fit"},
        400: {"description": "Invalid request framing"},
        408: {"description": "Request body timed out"},
        413: {"description": "Request body too large"},
        415: {"description": "Encoded request body is unsupported"},
        429: {"description": "Request rate exceeded; retry after the specified delay"},
        503: {"description": "Template unavailable or generation busy; retry if Retry-After is present"},
        500: {"description": "Preview failed"},
    },
)
def invitation_preview(recipient: RecipientRequest, request: Request) -> Response:
    """On-demand authoritative first-page preview; no recipient files are saved."""
    try:
        with generation_lock:
            invitation = generate_invitation(
                request.app.state.template,
                request.app.state.layout,
                RecipientText(recipient.name, recipient.second_line, recipient.city),
            )
            with pymupdf.open(stream=invitation.data, filetype="pdf") as document:
                image = document[0].get_pixmap(
                    matrix=pymupdf.Matrix(1.5, 1.5), alpha=False
                ).tobytes("png")
    except LayoutError as error:
        raise HTTPException(
            status_code=422, detail=str(error), headers={"Cache-Control": "no-store"}
        ) from None
    except TemplateError:
        raise HTTPException(
            status_code=503,
            detail="Invitation template is unavailable. Please try again later.",
            headers={"Cache-Control": "no-store"},
        ) from None
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to preview the invitation. Please try again later.",
            headers={"Cache-Control": "no-store"},
        ) from None
    return Response(
        image, media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/template/calibration", include_in_schema=False)
def template_calibration() -> FileResponse:
    return FileResponse(settings.calibration_page, media_type="text/html")


@router.post(
    "/invitations/single",
    response_class=Response,
    responses={
        200: {
            "description": "Four-page personalized invitation PDF.",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        422: {"description": "Invalid recipient fields or text that cannot fit at 16 pt."},
        400: {"description": "Invalid request framing."},
        408: {"description": "Request body timed out."},
        413: {"description": "Request body too large."},
        415: {"description": "Encoded request body is unsupported."},
        429: {"description": "Request rate exceeded; retry after the specified delay."},
        503: {"description": "Template unavailable or generation busy; retry if Retry-After is present."},
        500: {"description": "Invitation generation failed."},
    },
)
def single_invitation(recipient: RecipientRequest, request: Request) -> Response:
    try:
        with generation_lock:
            invitation = generate_invitation(
                request.app.state.template,
                request.app.state.layout,
                RecipientText(recipient.name, recipient.second_line, recipient.city),
            )
    except LayoutError as error:
        raise HTTPException(
            status_code=422, detail=str(error), headers={"Cache-Control": "no-store"}
        ) from None
    except TemplateError:
        raise HTTPException(
            status_code=503,
            detail="Invitation template is unavailable. Please try again later.",
            headers={"Cache-Control": "no-store"},
        ) from None
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to generate the invitation. Please try again later.",
            headers={"Cache-Control": "no-store"},
        ) from None

    fallback = invitation.filename if invitation.filename.isascii() else "Invitation.pdf"
    return Response(
        content=invitation.data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{fallback}"; '
                f"filename*=UTF-8''{quote(invitation.filename, safe='')}"
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )