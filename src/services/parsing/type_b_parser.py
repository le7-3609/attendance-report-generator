"""Parser for Type B attendance reports (דוח נוכחות מפורט עם שעות נוספות)."""
from __future__ import annotations

import logging
import re
from datetime import date, time

from src.constants import DATE_RE as _DATE_RE, FLOAT_RE as _FLOAT_RE
from src.constants import HEB_WEEKDAY_NAMES as _WEEKDAYS
from src.constants import TIME_RE as _TIME_RE
from src.domain.enums import ReportType
from src.domain.models import AttendanceRow, TypeBHeader
from src.services.parsing.base_parser import BaseParser
from src.services.parsing.hours_normalization import normalize_hours_token

logger = logging.getLogger(__name__)

_INT_RE = re.compile(r"\b(\d+)\b")

# Summary regexes
_DAYS_RE = re.compile(r"ימים[:\s]+(\d+)")
_TOTAL_HRS_RE = re.compile(r'סה[״"כ]+\s+שעות[:\s]+([\d.]+)')
_HRS100_RE = re.compile(r"שעות\s+100%[:\s]+([\d.]+)")
_HRS125_RE = re.compile(r"שעות\s+125%[:\s]+([\d.]+)")
_HRS150_RE = re.compile(r"שעות\s+150%[:\s]+([\d.]+)")
_COMPANY_RE = re.compile(r"(נ\.ע\.[^\n]+)")


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


class TypeBParser(BaseParser):
    """Parses Type B report text into ReportData."""

    report_type = ReportType.TYPE_B

    def _parse_summary(self, text: str) -> TypeBHeader:
        company = "נ.ע. הנשר בע\"מ"
        work_days = 0
        total_hours = 0.0
        hours_100 = 0.0
        hours_125 = 0.0
        hours_150 = 0.0

        m = _COMPANY_RE.search(text)
        if m:
            company = m.group(1).strip()
        m = _DAYS_RE.search(text)
        if m:
            work_days = int(m.group(1))
        m = _TOTAL_HRS_RE.search(text)
        if m:
            total_hours = normalize_hours_token(m.group(1))
        m = _HRS100_RE.search(text)
        if m:
            hours_100 = normalize_hours_token(m.group(1))
        m = _HRS125_RE.search(text)
        if m:
            hours_125 = normalize_hours_token(m.group(1))
        m = _HRS150_RE.search(text)
        if m:
            hours_150 = normalize_hours_token(m.group(1))
        return TypeBHeader(
            company=company,
            work_days=work_days,
            total_hours=total_hours,
            hours_100=hours_100,
            hours_125=hours_125,
            hours_150=hours_150,
        )

    def _is_header_line(self, line: str) -> bool:
        return any(token in line for token in ("תאריך", "כניסה", "יציאה", "הפסקה", "שעות 100", "שעות 125", "שעות 150"))

    def _parse_row(self, line: str) -> AttendanceRow | None:
        date_match = _DATE_RE.search(line)
        if not date_match:
            return None

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3))
        row_date = _safe_date(day, month, year)
        if not row_date:
            logger.warning("Skipping invalid date %02d/%02d/%04d", day, month, year)
            return None

        after = line[date_match.end() :]
        times = _TIME_RE.findall(after)

        entry_time = _safe_time(int(times[0][0]), int(times[0][1])) if len(times) >= 1 else None
        exit_time = _safe_time(int(times[1][0]), int(times[1][1])) if len(times) >= 2 else None
        break_time = _safe_time(int(times[2][0]), int(times[2][1])) if len(times) >= 3 else None

        floats = _FLOAT_RE.findall(after)
        total_hours = normalize_hours_token(floats[0]) if len(floats) >= 1 else 0.0
        hours_100 = normalize_hours_token(floats[1]) if len(floats) >= 2 else None
        hours_125 = normalize_hours_token(floats[2]) if len(floats) >= 3 else None
        hours_150 = normalize_hours_token(floats[3]) if len(floats) >= 4 else None

        weekday = ""
        for wd in _WEEKDAYS:
            if wd in line:
                weekday = wd
                break

        is_sabbath = (row_date.weekday() == 5) or weekday == "שבת"  # Saturday

        loc_text = _DATE_RE.sub("", line)
        loc_text = _TIME_RE.sub("", loc_text)
        loc_text = _FLOAT_RE.sub("", loc_text)
        loc_text = re.sub(r"\b\d+\b", "", loc_text)
        if weekday:
            loc_text = loc_text.replace(weekday, "")
        loc_text = re.sub(r"[|%.,/:;\\()\[\]{}]", " ", loc_text)
        location = " ".join(loc_text.split()) or None

        return AttendanceRow(
            date=row_date,
            weekday=weekday,
            entry_time=entry_time,
            exit_time=exit_time,
            break_time=break_time,
            location=location,
            total_hours=total_hours,
            hours_100=hours_100,
            hours_125=hours_125,
            hours_150=hours_150,
            is_sabbath=is_sabbath,
        )
