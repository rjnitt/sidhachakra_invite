"""Immutable template inspection and in-memory four-page PDF composition."""

import re
import unicodedata
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

import pymupdf

from app.models.schemas import TemplateLayout
from app.services.text_layout_service import RecipientText, TextLayoutService


class TemplateError(ValueError):
    """A template cannot be safely used by the application."""


@dataclass(frozen=True)
class GeneratedInvitation:
    data: bytes = field(repr=False)
    filename: str
    warnings: tuple[str, ...]


def invitation_filename(name: str, used_filenames: set[str] | None = None) -> str:
    stem = "".join(
        "_" if character in '<>:"/\\|?*' or unicodedata.category(character).startswith("C")
        else character
        for character in name
    )
    stem = re.sub(r"_+", "_", re.sub(r"\s+", "_", stem)).strip(" ._") or "Recipient"
    existing = {
        unicodedata.normalize("NFC", filename).casefold()
        for filename in used_filenames or ()
    }
    duplicate = 1
    while True:
        suffix = "" if duplicate == 1 else f"_{duplicate}"
        budget = 240 - len(f"Invitation_{suffix}.pdf".encode("utf-8"))
        short_stem = stem.encode("utf-8")[:budget].decode("utf-8", errors="ignore").rstrip(" ._")
        candidate = f"Invitation_{short_stem or 'Recipient'}{suffix}.pdf"
        if unicodedata.normalize("NFC", candidate).casefold() not in existing:
            if used_filenames is not None:
                used_filenames.add(candidate)
            return candidate
        duplicate += 1


@dataclass(frozen=True)
class Template:
    data: bytes = field(repr=False)
    inspection: dict

    def preview_png(self) -> bytes:
        with pymupdf.open(stream=self.data, filetype="pdf") as document:
            return document[0].get_pixmap(
                matrix=pymupdf.Matrix(1.5, 1.5), alpha=False
            ).tobytes("png")


def load_template(path: Path) -> Template:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise TemplateError("Invitation template is missing or unreadable.") from error

    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass:
                raise TemplateError("Invitation template must not be password-protected.")
            if document.page_count != 4:
                raise TemplateError("Invitation template must contain exactly four pages.")
            pages = [
                {
                    "page": page.number + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "rotation": page.rotation,
                    "media_box": list(page.mediabox),
                    "crop_box": list(page.cropbox),
                    "text_characters": len(page.get_text()),
                    "image_count": len(page.get_images()),
                }
                for page in document
            ]
    except TemplateError:
        raise
    except (RuntimeError, ValueError) as error:
        raise TemplateError("Invitation template is not a readable PDF.") from error

    return Template(
        data=data,
        inspection={
            "sha256": sha256(data).hexdigest(),
            "page_count": len(pages),
            "units": "PDF points (1/72 inch)",
            "pages": pages,
        },
    )


def generate_invitation(
    template: Template,
    configuration: TemplateLayout,
    recipient: RecipientText,
    used_filenames: set[str] | None = None,
) -> GeneratedInvitation:
    if sha256(template.data).hexdigest() != configuration.template_sha256:
        raise TemplateError("Template has changed and requires recalibration.")

    with pymupdf.open(stream=template.data, filetype="pdf") as document:
        first_page = document[0]
        if (
            document.page_count != 4
            or first_page.rotation != 0
            or abs(first_page.rect.width - configuration.page_width) > 0.001
            or abs(first_page.rect.height - configuration.page_height) > 0.001
        ):
            raise TemplateError("Template dimensions or page count require recalibration.")

        layout = TextLayoutService(configuration).fit(recipient)
        original_pages = [
            (tuple(page.mediabox), tuple(page.cropbox), page.rotation)
            for page in document
        ]
        box = configuration.text_box
        with pymupdf.open(stream=layout.overlay_pdf(), filetype="pdf") as overlay:
            first_page.show_pdf_page(
                pymupdf.Rect(box.x, box.y, box.x + box.width, box.y + box.height),
                overlay,
                overlay=True,
            )
        data = document.tobytes()

    with pymupdf.open(stream=data, filetype="pdf") as output:
        output_pages = [
            (tuple(page.mediabox), tuple(page.cropbox), page.rotation)
            for page in output
        ]
        if output.page_count != 4 or output_pages != original_pages:
            raise TemplateError("Generated invitation failed PDF integrity validation.")

    return GeneratedInvitation(
        data=data,
        filename=invitation_filename(recipient.name, used_filenames),
        warnings=layout.warnings,
    )