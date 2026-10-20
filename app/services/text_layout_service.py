"""Bundled-font HarfBuzz shaping and rule-aware, immutable text-only overlays."""

import unicodedata
from dataclasses import dataclass, field
from html import escape
from io import BytesIO
from pathlib import Path

import pymupdf

from app.core.config import PROJECT_ROOT
from app.models.schemas import TemplateLayout


class LayoutError(ValueError):
    """Recipient text cannot be rendered safely without changing its content."""


@dataclass(frozen=True)
class RecipientText:
    name: str
    second_line: str = ""
    city: str = ""


@dataclass(frozen=True)
class ShapedLine:
    text: str
    width: float
    height: float
    source_box: tuple[float, float, float, float]
    pdf: bytes = field(repr=False)


@dataclass(frozen=True)
class PositionedLine:
    field_index: int
    shaped: ShapedLine
    x: float
    y: float


@dataclass(frozen=True)
class TextLayout:
    recipient: RecipientText
    font_size: float
    lines: tuple[PositionedLine, ...]
    warnings: tuple[str, ...]
    width: float
    height: float

    def overlay_pdf(self) -> bytes:
        """Return a transparent, text-only PDF, not a personalized invitation."""
        with pymupdf.open() as document:
            page = document.new_page(width=self.width, height=self.height)
            for line in self.lines:
                with pymupdf.open(stream=line.shaped.pdf, filetype="pdf") as source:
                    page.show_pdf_page(
                        pymupdf.Rect(
                            line.x, line.y,
                            line.x + line.shaped.width, line.y + line.shaped.height,
                        ),
                        source,
                        clip=pymupdf.Rect(line.shaped.source_box),
                    )
            return document.tobytes()

    def overlay_png(self, scale: float = 4) -> bytes:
        if not 1 <= scale <= 8:
            raise ValueError("Preview scale must be between 1 and 8.")
        with pymupdf.open(stream=self.overlay_pdf(), filetype="pdf") as document:
            return document[0].get_pixmap(
                matrix=pymupdf.Matrix(scale, scale), alpha=True
            ).tobytes("png")


class TextLayoutService:
    def __init__(
        self,
        configuration: TemplateLayout,
        font_directory: Path = PROJECT_ROOT / "assets" / "fonts",
    ) -> None:
        self.configuration = configuration
        self.font_directory = font_directory
        try:
            font_data = (font_directory / "NotoSansDevanagari.ttf").read_bytes()
            self.font = pymupdf.Font(
                fontbuffer=font_data
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise LayoutError("The bundled invitation font is unavailable.") from error

    def _validate(self, recipient: RecipientText) -> list[tuple[int, str]]:
        values = (recipient.name, recipient.second_line, recipient.city)
        if not all(isinstance(value, str) for value in values):
            raise LayoutError("Recipient fields must be text strings.")
        if not recipient.name.strip():
            raise LayoutError("Name is required.")
        if any(len(value) > 500 for value in values):
            raise LayoutError("Each recipient field must not exceed 500 characters.")
        for value in values:
            for character in value:
                if character in ("\u200c", "\u200d"):
                    continue
                if unicodedata.category(character).startswith("C") or character in ("\u2028", "\u2029"):
                    raise LayoutError("Recipient fields must be single-line text without controls.")
                if not character.isspace() and not self.font.has_glyph(ord(character)):
                    raise LayoutError("Recipient text contains a character not supported by the bundled font.")
        return [(index, value) for index, value in enumerate(values) if value.strip()]

    def _shape(self, text: str, size: float) -> ShapedLine:
        page_width = max(600, len(text) * size * 2 + 64)
        page_height = size * 6 + 64
        story = pymupdf.Story(
            html=f"<p>{escape(text)}</p>",
            user_css=f"""
                @font-face {{ font-family: Invitation; src: url(NotoSansDevanagari.ttf); }}
                body {{ margin: 0; font-family: Invitation; font-size: {size}pt; color: {self.configuration.color}; }}
                p {{ margin: 0; white-space: pre; line-height: 1.5; }}
            """,
            archive=pymupdf.Archive(str(self.font_directory)),
        )
        output = BytesIO()
        with pymupdf.DocumentWriter(output) as writer:
            device = writer.begin_page(pymupdf.Rect(0, 0, page_width, page_height))
            more, filled = story.place(pymupdf.Rect(32, 32, page_width - 32, page_height - 32))
            if more:
                raise LayoutError("Text shaping exceeded its safe measurement area.")
            story.draw(device)
            writer.end_page()

        with pymupdf.open(stream=output.getvalue(), filetype="pdf") as document:
            spans = [
                span
                for block in document[0].get_text("dict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
            ]
            if not spans:
                raise LayoutError("Recipient text did not produce visible glyphs.")
            bounds = pymupdf.Rect(spans[0]["bbox"])
            for span in spans[1:]:
                bounds |= pymupdf.Rect(span["bbox"])
            bounds += (-0.5, -0.5, 0.5, 0.5)
            if any(
                "NotoSansDevanagari" not in font[3].replace(" ", "")
                for font in document[0].get_fonts()
            ):
                raise LayoutError("Text rendering attempted to use an unbundled fallback font.")
            document.subset_fonts()
            return ShapedLine(
                text, bounds.width, bounds.height, tuple(bounds), document.tobytes()
            )

    def _position(
        self, shaped: list[tuple[int, ShapedLine]], size: float
    ) -> tuple[PositionedLine, ...] | None:
        box = self.configuration.text_box
        if any(line.width > box.width or line.height > box.height for index, line in shaped):
            return None
        spacing = size * self.configuration.line_spacing
        lines = tuple(
            PositionedLine(field_index, line, (box.width - line.width) / 2, 1 + index * spacing)
            for index, (field_index, line) in enumerate(shaped)
        )
        if any(line.y + line.shaped.height > box.height for line in lines):
            return None
        if any(
            box.y + line.y < end and box.y + line.y + line.shaped.height > start
            for line in lines
            for start, end in self.configuration.excluded_y_ranges
        ):
            return None
        return lines

    def fit(self, recipient: RecipientText) -> TextLayout:
        fields = self._validate(recipient)
        configuration = self.configuration
        size = configuration.font_size
        shaped = [(index, self._shape(text, size)) for index, text in fields]
        lines = self._position(shaped, size)
        if lines is None:
            raise LayoutError(
                "Recipient text cannot fit safely at 16 pt. Shorten the entry manually; "
                "automatic shrinking and wrapping are disabled."
            )
        return TextLayout(
            recipient, size, lines, (), configuration.text_box.width, configuration.text_box.height
        )