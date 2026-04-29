"""Maps ReportType to the appropriate transformation strategy."""
from __future__ import annotations

from src.domain.enums import ReportType
from src.services.variation.type_a_variator import TypeAVariator
from src.services.variation.type_b_variator import TypeBVariator
from src.services.variation.validating_decorator import ValidatingVariatorDecorator
from src.services.variation.transformation_service import TransformationService
from src.services.variation.base_strategy import BaseTransformationStrategy
from src.services.variation.base_variator import BaseVariator


_REGISTRY: dict[ReportType, BaseTransformationStrategy] = {
    ReportType.TYPE_A: ValidatingVariatorDecorator(TypeAVariator()),
    ReportType.TYPE_B: ValidatingVariatorDecorator(TypeBVariator()),
}


def get_strategy(report_type: ReportType) -> BaseTransformationStrategy:
    strategy = _REGISTRY.get(report_type)
    if strategy is None:
        raise ValueError(f"No strategy registered for report type: {report_type}")
    return strategy


def get_transformation_service() -> TransformationService:
    return TransformationService(strategy_registry=_REGISTRY)


def get_variator(report_type: ReportType) -> BaseVariator:
    """Backwards-compatible adapter for older callers.

    Prefer `get_transformation_service().transform(data)` for the new pipeline.
    """
    strategy = get_strategy(report_type)
    if not isinstance(strategy, BaseVariator):
        raise TypeError(f"Registered strategy for {report_type} does not implement BaseVariator.")
    return strategy
