"""Strategy interface for row-level transformations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.domain.models import AttendanceRow, ReportData


class BaseTransformationStrategy(ABC):
    @abstractmethod
    def transform_row(self, row: AttendanceRow) -> AttendanceRow:
        """Transform a single row. May raise TransformationError on invalid output."""

    @abstractmethod
    def finalize(self, data: ReportData, rows: Sequence[AttendanceRow]) -> ReportData:
        """Finalize a transformed report (e.g. recompute header totals)."""

