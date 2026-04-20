"""Parser for Type A attendance reports (דוח נוכחות חודשי)."""
from __future__ import annotations

import logging
import re
from datetime import date, time

from src.constants import DATE_RE as _DATE_RE, FLOAT_RE as _FLOAT_RE
from src.constants import HEB_MONTHS as _HEB_MONTHS, HEB_WEEKDAY_NAMES as _WEEKDAYS
from src.constants import TIME_RE as _TIME_RE
from src.domain.enums import ReportType
from src.domain.models import AttendanceRow, ReportData, TypeAHeader
from src.services.parsing.base_parser import BaseParser

logger = logging.getLogger(__name__)

# Summary patterns
_WORK_DAYS_RE = re.compile(r"ימי\s+עבודה\s+לחודש[:\s]+(\d+)")
_TOTAL_HRS_RE = re.compile(r'סה[\u05f4"\u05f3״׳״"כ]+\s+שעות\s+חודשי[ו]?ת[:\s]+(\d+\.?\d*)')
_HOURLY_RATE_RE = re.compile(r'מחיר\s+לשעה[:\s\u20aa]*(\d+\.?\d*)')
_TOTAL_PAY_RE = re.compile(r'סה[\u05f4"\u05f3״׳״"כ]+\s+לתשלום[:\s\u20aa]*(\d+\.?\d*)')


def _safe_date(day: int, month: int, year: int) -> date | None:
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _safe_time(h: int, m: int) -> time | None:
    try:
        return time(h, m)
    except ValueError:
        return None


class TypeAParser(BaseParser):
    """Parses Type A report text into ReportData."""

    def parse(self, text: str, source_filename: str = "") -> ReportData:
        header = self._parse_header(text)
        rows = self._parse_rows(text)

        # If we got rows but header has no month label, derive it from first valid date
        if not header.month_label and rows:
            first_date = next((r.date for r in rows if r.date), None)
            if first_date:
                header.month_label = f"{_HEB_MONTHS.get(first_date.month, '')} {first_date.year}"

        # If header fields are zero, derive from rows
        if header.work_days == 0:
            header.work_days = sum(1 for r in rows if r.date)
        if header.total_hours == 0.0:
            header.total_hours = round(sum(r.total_hours for r in rows), 2)

        return ReportData(
            report_type=ReportType.TYPE_A,
            header=header,
            rows=rows,
            source_filename=source_filename,
        )

    # ------------------------------------------------------------------
    def _parse_header(self, text: str) -> TypeAHeader:
        h = TypeAHeader()
        m = _WORK_DAYS_RE.search(text)
        if m:
            h.work_days = int(m.group(1))
        m = _TOTAL_HRS_RE.search(text)
        if m:
            try:
                h.total_hours = float(m.group(1))
            except ValueError:
                pass
        m = _HOURLY_RATE_RE.search(text)
        if m:
            try:
                h.hourly_rate = float(m.group(1))
            except ValueError:
                pass
        m = _TOTAL_PAY_RE.search(text)
        if m:
            try:
                h.total_pay = float(m.group(1))
            except ValueError:
                pass
        return h

    def _parse_rows(self, text: str) -> list[AttendanceRow]:
        rows: list[AttendanceRow] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Each data row should contain a date pattern
            date_match = _DATE_RE.search(line)
            if not date_match:
                continue

            day, month, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            # Sanity-check: day/month must be plausible calendar values
            if not (1 <= day <= 31 and 1 <= month <= 12):
                continue
            row_date = _safe_date(day, month, year)
            if not row_date:
                logger.warning("Skipping row with invalid date %02d/%02d/%04d", day, month, year)
                continue

            # Extract times — first two HH:MM matches after the date
            after_date = line[date_match.end():]
            time_iter = list(_TIME_RE.finditer(after_date))
            times = _TIME_RE.findall(after_date)
            entry_time = _safe_time(int(times[0][0]), int(times[0][1])) if len(times) >= 1 else None
            exit_time = _safe_time(int(times[1][0]), int(times[1][1])) if len(times) >= 2 else None

            # Extract total hours: take the first float that appears *after*
            # the last time token.  This avoids picking up OCR noise that may
            # appear elsewhere on the line (e.g. a year or price figure).
            after_times_offset = time_iter[-1].end() if time_iter else 0
            floats_after_times = _FLOAT_RE.findall(after_date[after_times_offset:])
            total_hours = float(floats_after_times[0]) if floats_after_times else 0.0

            # Weekday name
            weekday = ""
            for wd in _WEEKDAYS:
                if wd in line:
                    weekday = wd
                    break

            rows.append(AttendanceRow(
                date=row_date,
                weekday=weekday,
                entry_time=entry_time,
                exit_time=exit_time,
                total_hours=total_hours,
            ))

        return rows
