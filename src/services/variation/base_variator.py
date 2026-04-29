"""Abstract base variator."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import ReportData


class BaseVariator(ABC):

    @abstractmethod
    def vary(self, data: ReportData) -> ReportData:
        """Apply realistic variations to *data* and return new ReportData.

        The original *data* object is never modified — frozen dataclasses
        enforce this at runtime. Per-row determinism is achieved by seeding
        the RNG from each row's date inside the concrete implementation.
        """
