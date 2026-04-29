"""Row transformation orchestration.

The service knows *nothing* about concrete report types. It selects a strategy
from the registry and applies it row-by-row with a safe fallback:

- If a strategy (or its validation decorator) raises TransformationError for a row,
  the service keeps the original row and continues.
"""
from __future__ import annotations

from collections.abc import Mapping

from src.domain.enums import ReportType
from src.domain.exceptions import TransformationError
from src.domain.models import ReportData
from src.services.variation.base_strategy import BaseTransformationStrategy


class TransformationService:
    def __init__(self, *, strategy_registry: Mapping[ReportType, BaseTransformationStrategy]) -> None:
        self._registry = dict(strategy_registry)

    def transform(self, data: ReportData) -> ReportData:
        strategy = self._registry.get(data.report_type)
        if strategy is None:
            raise ValueError(f"No strategy registered for report type: {data.report_type}")

        out_rows = []
        for row in data.rows:
            try:
                out_rows.append(strategy.transform_row(row))
            except TransformationError:
                out_rows.append(row)

        return strategy.finalize(data, out_rows)

