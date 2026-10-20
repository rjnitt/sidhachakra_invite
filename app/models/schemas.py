"""Validated consecutive-row placement and fixed 16-point typography."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecipientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=500)
    second_line: str = Field(default="", max_length=500)
    city: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def require_visible_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required.")
        return value


class TextBox(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class TemplateLayout(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    status: Literal["pending_approval", "placement_approved"]
    template_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: Literal[1]
    coordinate_system: Literal["pdf_points"]
    origin: Literal["top_left"]
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    text_box: TextBox
    alignment: Literal["center"]
    vertical_alignment: Literal["writing_rows"]
    color: Literal["#800020"]
    font_family: str
    font_size: Literal[16]
    minimum_font_size: Literal[16]
    line_spacing: float = Field(gt=0)
    excluded_y_ranges: list[tuple[float, float]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bounds(self) -> "TemplateLayout":
        if self.text_box.x + self.text_box.width > self.page_width:
            raise ValueError("Text box extends beyond page width.")
        if self.text_box.y + self.text_box.height > self.page_height:
            raise ValueError("Text box extends beyond page height.")
        if self.minimum_font_size > self.font_size:
            raise ValueError("Minimum font size exceeds base font size.")
        if any(
            not 0 <= start < end <= self.page_height
            for start, end in self.excluded_y_ranges
        ):
            raise ValueError("Excluded rule bands must be inside the page.")
        return self

    def public_configuration(self) -> dict:
        configuration = self.model_dump(exclude={"template_sha256"})
        configuration["coordinate_system"] = "normalized"
        configuration["pdf_text_box"] = self.text_box.model_dump()
        configuration["font_size_units"] = "pdf_points"
        configuration["text_box"] = {
            "x": self.text_box.x / self.page_width,
            "y": self.text_box.y / self.page_height,
            "width": self.text_box.width / self.page_width,
            "height": self.text_box.height / self.page_height,
        }
        return configuration