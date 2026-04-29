"""Template-method base parser.

Concrete parsers implement only the parts that vary per report type:
- `_parse_summary()` extracts the report header/summary.
- `_parse_row()` converts one line into an AttendanceRow (or returns None).
- `_is_header_line()` filters out table header/garbage lines during row parsing.

The public `parse()` method defines the fixed sequence of steps.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import dataclasses
from typing import Iterable, TypeVar

from src.constants import HEB_MONTHS as _HEB_MONTHS
from src.domain.enums import ReportType
from src.domain.exceptions import ParseError
from src.domain.models import AttendanceRow, ReportData, TypeAHeader, TypeBHeader

_HeaderT = TypeVar("_HeaderT", TypeAHeader, TypeBHeader)


class BaseParser(ABC):

    report_type: ReportType

    def parse(self, text: str, source_filename: str = "") -> ReportData:
        """Parse extracted text into a structured ReportData object."""
        if not text or not text.strip():
            raise ParseError(f"Empty text provided to {self.__class__.__name__}.")

        header = self._parse_summary(text)
        rows = tuple(self._parse_rows(text))
        header = self._derive_missing_header_fields(header, rows)

        return ReportData(
            report_type=self.report_type,
            header=header,
            rows=rows,
            source_filename=source_filename,
        )

    # ------------------------------------------------------------------
    @abstractmethod
    def _parse_summary(self, text: str) -> _HeaderT:
        raise NotImplementedError

    @abstractmethod
    def _parse_row(self, line: str) -> AttendanceRow | None:
        raise NotImplementedError

    @abstractmethod
    def _is_header_line(self, line: str) -> bool:
        raise NotImplementedError

    def _parse_rows(self, text: str) -> Iterable[AttendanceRow]:
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if self._is_header_line(line):
                continue
            row = self._parse_row(line)
            if row is not None:
                yield row

    def _derive_missing_header_fields(
        self, header: _HeaderT, rows: tuple[AttendanceRow, ...]
    ) -> _HeaderT:
        """Fill common derived header fields without per-type branching in parsers."""
        # month_label: derive from first valid date.
        if hasattr(header, "month_label") and not getattr(header, "month_label", "") and rows:
            first_date = next((r.date for r in rows if r.date), None)
            if first_date is not None:
                header = dataclasses.replace(
                    header,
                    month_label=f"{_HEB_MONTHS.get(first_date.month, '')} {first_date.year}",
                )

        # work_days: Type A counts all dated rows; Type B excludes sabbath rows.
        if hasattr(header, "work_days") and not getattr(header, "work_days", 0):
            if self.report_type == ReportType.TYPE_B:
                work_days = sum(1 for r in rows if r.date and not bool(r.is_sabbath))
            else:
                work_days = sum(1 for r in rows if r.date)
            header = dataclasses.replace(header, work_days=work_days)

        # total_hours
        if hasattr(header, "total_hours") and not getattr(header, "total_hours", 0.0):
            header = dataclasses.replace(
                header, total_hours=round(sum((r.total_hours or 0.0) for r in rows), 2)
            )

        # Type B tier totals if present on header.
        if self.report_type == ReportType.TYPE_B:
            if hasattr(header, "hours_100") and not getattr(header, "hours_100", 0.0):
                header = dataclasses.replace(
                    header, hours_100=round(sum((r.hours_100 or 0.0) for r in rows), 2)
                )
            if hasattr(header, "hours_125") and not getattr(header, "hours_125", 0.0):
                header = dataclasses.replace(
                    header, hours_125=round(sum((r.hours_125 or 0.0) for r in rows), 2)
                )
            if hasattr(header, "hours_150") and not getattr(header, "hours_150", 0.0):
                header = dataclasses.replace(
                    header, hours_150=round(sum((r.hours_150 or 0.0) for r in rows), 2)
                )

        return header
