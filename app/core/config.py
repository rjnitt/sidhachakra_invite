"""Minimal, immutable application configuration."""

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Jain Invitation Personalizer"
    version: str = "0.0.1"
    template_path: Path = PROJECT_ROOT / "assets" / "invitation.pdf"
    layout_path: Path = PROJECT_ROOT / "config" / "layout.json"
    calibration_page: Path = PROJECT_ROOT / "frontend" / "calibration.html"
    frontend_path: Path = PROJECT_ROOT / "frontend"
    font_path: Path = PROJECT_ROOT / "assets" / "fonts" / "NotoSansDevanagari.ttf"


settings = Settings()