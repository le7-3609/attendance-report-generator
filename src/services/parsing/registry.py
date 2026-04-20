"""Maps ReportType to the appropriate parser."""
from __future__ import annotations

from src.domain.enums import ReportType
from src.services.parsing.base_parser import BaseParser
from src.services.parsing.type_a_parser import TypeAParser
from src.services.parsing.type_b_parser import TypeBParser


_REGISTRY: dict[ReportType, BaseParser] = {
    ReportType.TYPE_A: TypeAParser(),
    ReportType.TYPE_B: TypeBParser(),
}


def get_parser(report_type: ReportType) -> BaseParser:
    parser = _REGISTRY.get(report_type)
    if parser is None:
        raise ValueError(f"No parser registered for report type: {report_type}")
    return parser
