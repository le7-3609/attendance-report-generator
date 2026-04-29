"""Domain models for attendance reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from src.domain.enums import ReportType


@dataclass(frozen=True)
class AttendanceRow:
    """A single day row in an attendance report."""

    date: Optional[date] = None
    weekday: str = ""           # Hebrew day name, e.g. "ראשון"
    entry_time: Optional[time] = None
    exit_time: Optional[time] = None
    break_time: Optional[time] = None   # Type B only
    location: str = ""          # Type B only (מקום ע"נ)
    total_hours: float = 0.0
    hours_100: float = 0.0      # Type B: regular hours
    hours_125: float = 0.0      # Type B: overtime 125%
    hours_150: float = 0.0      # Type B: overtime 150%
    notes: str = ""             # Type A only
    is_sabbath: bool = False    # Type B: Saturday flag


@dataclass(frozen=True)
class TypeAHeader:
    """Summary fields for a Type A report."""

    work_days: int = 0
    total_hours: float = 0.0
    hourly_rate: float = 0.0
    total_pay: float = 0.0
    month_label: str = ""       # e.g. "ינואר 2023"


@dataclass(frozen=True)
class TypeBHeader:
    """Summary fields for a Type B report."""

    company: str = "נ.ע. הנשר בע\"מ"
    employee_name: str = ""
    month_label: str = ""
    work_days: int = 0
    total_hours: float = 0.0
    hours_100: float = 0.0
    hours_125: float = 0.0
    hours_150: float = 0.0
    bonus: float = 0.0
    travel: float = 0.0


@dataclass(frozen=True)
class ReportData:
    """Full, typed report ready for variation and rendering."""

    report_type: ReportType
    header: TypeAHeader | TypeBHeader
    rows: tuple[AttendanceRow, ...] = field(default_factory=tuple)
    source_filename: str = ""
