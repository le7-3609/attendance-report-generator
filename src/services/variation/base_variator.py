"""Abstract base variator."""
from __future__ import annotations

from abc import abstractmethod

from src.domain.exceptions import TransformationError
from src.domain.models import ReportData
from src.services.variation.base_strategy import BaseTransformationStrategy


class BaseVariator(BaseTransformationStrategy):
    """Extends BaseTransformationStrategy with a concrete vary() entry-point.

    Subclasses implement transform_row() and finalize(); the loop with
    safe per-row fallback lives here once.
    """

    def vary(self, data: ReportData) -> ReportData:
        out = []
        for row in data.rows:
            try:
                out.append(self.transform_row(row))
            except TransformationError:
                out.append(row)
        return self.finalize(data, out)

    @abstractmethod
    def transform_row(self, row):  # type: ignore[override]
        ...

    @abstractmethod
    def finalize(self, data, rows):  # type: ignore[override]
        ...
