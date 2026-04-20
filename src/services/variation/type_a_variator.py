"""Type A variation logic — adjusts entry/exit times within business rules."""
from __future__ import annotations

import copy
import logging
import random
from datetime import date, datetime, time, timedelta

from src.constants import HEB_WEEKDAYS as _HEB_WEEKDAYS
from src.domain.models import AttendanceRow, ReportData, TypeAHeader
from src.services.variation.base_variator import BaseVariator

logger = logging.getLogger(__name__)

# Constraints for Type A (short shifts, morning or midday)
_MIN_ENTRY = time(7, 0)
_MAX_ENTRY = time(10, 0)
_MIN_SHIFT_H = 2.0   # hours
_MAX_SHIFT_H = 5.0   # hours
_ENTRY_DELTA_MINUTES = 15   # max ± adjustment on entry
_EXIT_DELTA_MINUTES = 10    # max ± adjustment on exit


def _to_datetime(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def _clamp_time(t: time, lo: time, hi: time) -> time:
    if t < lo:
        return lo
    if t > hi:
        return hi
    return t


def _add_minutes(t: time, minutes: int) -> time:
    dt = datetime(2000, 1, 1, t.hour, t.minute) + timedelta(minutes=minutes)
    return dt.time()


def _hours_between(t1: time, t2: time) -> float:
    dt1 = datetime(2000, 1, 1, t1.hour, t1.minute)
    dt2 = datetime(2000, 1, 1, t2.hour, t2.minute)
    if dt2 <= dt1:
        dt2 += timedelta(days=1)
    return round((dt2 - dt1).total_seconds() / 3600, 2)


class TypeAVariator(BaseVariator):
    """Applies realistic random variations to a Type A report."""

    def vary(self, data: ReportData, *, seed: int | None = None) -> ReportData:
        if seed is not None:
            random.seed(seed)
        result = copy.deepcopy(data)
        new_rows: list[AttendanceRow] = []

        for row in result.rows:
            if row.date is None:
                continue

            # If OCR failed to extract times, synthesise plausible ones
            if row.entry_time is None or row.exit_time is None:
                logger.debug("Synthesising times for incomplete row (date=%s).", row.date)
                row.entry_time = _clamp_time(
                    time(8, random.randint(0, 30)), _MIN_ENTRY, _MAX_ENTRY
                )
                row.exit_time = _add_minutes(row.entry_time, int(_MIN_SHIFT_H * 60))

            original_duration_h = _hours_between(row.entry_time, row.exit_time)

            # Adjust entry time
            delta_entry = random.randint(-_ENTRY_DELTA_MINUTES, _ENTRY_DELTA_MINUTES)
            new_entry = _clamp_time(_add_minutes(row.entry_time, delta_entry), _MIN_ENTRY, _MAX_ENTRY)

            # Adjust shift duration within valid range
            target_duration_h = max(
                _MIN_SHIFT_H,
                min(_MAX_SHIFT_H, original_duration_h + random.uniform(-0.25, 0.25)),
            )
            delta_exit = random.randint(-_EXIT_DELTA_MINUTES, _EXIT_DELTA_MINUTES)
            raw_exit = _add_minutes(
                new_entry, int(target_duration_h * 60) + delta_exit
            )

            # Ensure exit > entry and total hours in valid range
            actual_h = _hours_between(new_entry, raw_exit)
            if actual_h < _MIN_SHIFT_H:
                raw_exit = _add_minutes(new_entry, int(_MIN_SHIFT_H * 60))
            elif actual_h > _MAX_SHIFT_H:
                raw_exit = _add_minutes(new_entry, int(_MAX_SHIFT_H * 60))

            row.entry_time = new_entry
            row.exit_time = raw_exit
            row.total_hours = _hours_between(new_entry, raw_exit)

            # Recalculate weekday from the actual date (fixes OCR errors in original)
            row.weekday = _HEB_WEEKDAYS.get(row.date.weekday(), "")

            new_rows.append(row)

        result.rows = new_rows

        # Recalculate header totals
        header: TypeAHeader = result.header  # type: ignore[assignment]
        header.work_days = len(new_rows)
        header.total_hours = round(sum(r.total_hours for r in new_rows), 2)

        # If OCR did not extract an hourly rate, synthesise a plausible one
        # (Israeli minimum wage range + common rates: ₪33–₪65/h)
        if not header.hourly_rate:
            header.hourly_rate = round(random.uniform(33.0, 65.0), 2)

        # Always recalculate total pay from the varied hours and rate
        header.total_pay = round(header.total_hours * header.hourly_rate, 2)

        return result
