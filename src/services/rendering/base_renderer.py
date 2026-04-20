"""Abstract base renderer."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import ReportData


class BaseRenderer(ABC):

    @abstractmethod
    def render(self, data: ReportData) -> str:
        """Render *data* to an HTML string."""
