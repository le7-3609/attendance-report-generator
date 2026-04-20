"""Maps ReportType to the appropriate renderer."""
from __future__ import annotations

from src.domain.enums import ReportType
from src.services.rendering.base_renderer import BaseRenderer
from src.services.rendering.type_a_renderer import TypeARenderer
from src.services.rendering.type_b_renderer import TypeBRenderer


_REGISTRY: dict[ReportType, BaseRenderer] = {
    ReportType.TYPE_A: TypeARenderer(),
    ReportType.TYPE_B: TypeBRenderer(),
}


def get_renderer(report_type: ReportType) -> BaseRenderer:
    renderer = _REGISTRY.get(report_type)
    if renderer is None:
        raise ValueError(f"No renderer registered for report type: {report_type}")
    return renderer
