"""Abstract base parser."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import ReportData


class BaseParser(ABC):

    @abstractmethod
    def parse(self, text: str, source_filename: str = "") -> ReportData:
        """Parse extracted text into a structured ReportData object."""
