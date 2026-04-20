"""Abstract base variator."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import ReportData


class BaseVariator(ABC):

    @abstractmethod
    def vary(self, data: ReportData, *, seed: int | None = None) -> ReportData:
        """Apply realistic variations to *data* and return new ReportData.

        Parameters
        ----------
        data:
            The parsed report to vary.
        seed:
            Optional RNG seed for reproducible output.  Pass the same seed
            with the same input to get identical variations every time.
        """
