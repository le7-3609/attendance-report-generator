"""Renderer for Type B attendance reports."""
from __future__ import annotations

from src.services.rendering.type_a_renderer import TypeARenderer


class TypeBRenderer(TypeARenderer):
    """Renders a Type B ReportData as an HTML string using Jinja2."""

    def __init__(self) -> None:
        super().__init__(template_name="type_b.html.j2")
