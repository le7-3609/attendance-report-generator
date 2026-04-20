"""Maps ReportType to the appropriate variator."""
from __future__ import annotations

from src.domain.enums import ReportType
from src.services.variation.base_variator import BaseVariator
from src.services.variation.type_a_variator import TypeAVariator
from src.services.variation.type_b_variator import TypeBVariator


_REGISTRY: dict[ReportType, BaseVariator] = {
    ReportType.TYPE_A: TypeAVariator(),
    ReportType.TYPE_B: TypeBVariator(),
}


def get_variator(report_type: ReportType) -> BaseVariator:
    variator = _REGISTRY.get(report_type)
    if variator is None:
        raise ValueError(f"No variator registered for report type: {report_type}")
    return variator
