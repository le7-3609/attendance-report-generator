"""Renderer for Type A attendance reports."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.domain.models import ReportData
from src.services.rendering.base_renderer import BaseRenderer

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"


class TypeARenderer(BaseRenderer):
    """Renders a ReportData as an HTML string using a Jinja2 template.

    Accepts an explicit *template_name* so that subclasses (e.g. TypeBRenderer)
    can reuse this implementation without duplicating code.
    """

    def __init__(self, template_name: str = "type_a.html.j2") -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        self._template_name = template_name

    def render(self, data: ReportData) -> str:
        template = self._env.get_template(self._template_name)
        return template.render(header=data.header, rows=data.rows)
