"""Base class for PDF text extractors."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseExtractor(ABC):

    @abstractmethod
    def extract(self, pdf_bytes: bytes) -> str:
        """Return the text content of the PDF as a single string."""
