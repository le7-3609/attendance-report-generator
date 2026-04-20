"""Type B variation logic — adjusts times and recalculates overtime tiers."""
from __future__ import annotations

import copy
import logging
import random
from datetime import date, datetime, time, timedelta

from src.constants import HEB_WEEKDAYS as _HEB_WEEKDAYS
from src.domain.models import AttendanceRow, ReportData, TypeBHeader
from src.services.variation.base_variator import BaseVariator

logger = logging.getLogger(__name__)

# Overtime tier thresholds (Israeli labor law defaults)
_REGULAR_THRESHOLD = 8.0    # first 8h at 100%
_OT_125_HOURS = 2.0         # next 2h at 125%
# remainder at 150%

_ENTRY_DELTA_MINUTES = 10
_EXIT_DELTA_MINUTES = 10
_MIN_SHIFT_H = 1.0
_MAX_SHIFT_H = 16.0

_DEFAULT_LOCATIONS = [
    "תל אביב", "ירושלים", "חיפה", "ראשון לציון",
    "פתח תקווה", "אשדוד", "נתניה", "באר שבע",
]


def _add_minutes(t: time, minutes: int) -> time:
    dt = datetime(2000, 1, 2, t.hour, t.minute) + timedelta(minutes=minutes)
    return dt.time()


def _hours_between(t1: time, t2: time) -> float:
    dt1 = datetime(2000, 1, 2, t1.hour, t1.minute)
    dt2 = datetime(2000, 1, 2, t2.hour, t2.minute)
    if dt2 <= dt1:
        dt2 += timedelta(days=1)
    return round((dt2 - dt1).total_seconds() / 3600, 2)


def _calc_break(break_time: time | None) -> float:
    if break_time is None:
        return 0.0
    return break_time.hour + break_time.minute / 60.0


def _split_overtime(net_hours: float) -> tuple[float, float, float]:
    """Split net working hours into 100% / 125% / 150% tiers."""
    h100 = min(net_hours, _REGULAR_THRESHOLD)
    h125 = min(max(net_hours - _REGULAR_THRESHOLD, 0.0), _OT_125_HOURS)
    h150 = max(net_hours - _REGULAR_THRESHOLD - _OT_125_HOURS, 0.0)
    return round(h100, 2), round(h125, 2), round(h150, 2)


class TypeBVariator(BaseVariator):
    """Applies realistic random variations to a Type B report."""

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
                row.entry_time = time(8, random.randint(0, 30))
                # ~20 % of synthesised shifts exceed 10 h (net) so 150 % overtime fires
                if random.random() < 0.20:
                    row.exit_time = time(random.randint(19, 20), random.randint(0, 59))
                else:
                    row.exit_time = time(random.randint(16, 18), random.randint(0, 59))

            original_gross_h = _hours_between(row.entry_time, row.exit_time)
            break_h = _calc_break(row.break_time)

            # Adjust entry
            delta_entry = random.randint(-_ENTRY_DELTA_MINUTES, _ENTRY_DELTA_MINUTES)
            new_entry = _add_minutes(row.entry_time, delta_entry)

            # Adjust exit (keep original gross duration ± small delta)
            delta_exit = random.randint(-_EXIT_DELTA_MINUTES, _EXIT_DELTA_MINUTES)
            target_gross_minutes = int(original_gross_h * 60) + delta_exit
            # ~15 % of weekday rows get a long shift so the 150 % tier fires
            if random.random() < 0.15 and row.date.weekday() != 5:
                target_gross_minutes = random.randint(int(10.5 * 60), int(12 * 60))
            target_gross_minutes = max(int(_MIN_SHIFT_H * 60), target_gross_minutes)
            target_gross_minutes = min(int(_MAX_SHIFT_H * 60), target_gross_minutes)
            new_exit = _add_minutes(new_entry, target_gross_minutes)

            # Vary break time. Treat time(0,0) the same as None — OCR often
            # reads an empty break cell as "00:00", which is not a real break.
            has_real_break = (
                row.break_time is not None
                and (row.break_time.hour > 0 or row.break_time.minute > 0)
            )
            if has_real_break:
                break_delta = random.randint(-5, 5)
                new_break_minutes = max(1, min(1439, row.break_time.hour * 60 + row.break_time.minute + break_delta))  # type: ignore[union-attr]
                row.break_time = time(new_break_minutes // 60, new_break_minutes % 60)
                break_h = new_break_minutes / 60.0
            else:
                # Synthesise a plausible break: 20–45 minutes
                break_minutes = random.randint(20, 45)
                row.break_time = time(0, break_minutes)
                break_h = break_minutes / 60.0

            # Net hours = gross − break
            net_h = round(_hours_between(new_entry, new_exit) - break_h, 2)
            net_h = max(0.0, net_h)

            row.entry_time = new_entry
            row.exit_time = new_exit
            row.total_hours = net_h
            row.hours_100, row.hours_125, row.hours_150 = _split_overtime(net_h)

            # Assign fallback location when OCR did not extract one
            if not row.location:
                row.location = random.choice(_DEFAULT_LOCATIONS)

            # Recalculate weekday
            row.weekday = _HEB_WEEKDAYS.get(row.date.weekday(), "")
            row.is_sabbath = row.date.weekday() == 5

            new_rows.append(row)

        result.rows = new_rows

        # Recalculate summary
        header: TypeBHeader = result.header  # type: ignore[assignment]
        header.work_days = sum(1 for r in new_rows if not r.is_sabbath)
        header.total_hours = round(sum(r.total_hours for r in new_rows), 2)
        header.hours_100 = round(sum(r.hours_100 for r in new_rows), 2)
        header.hours_125 = round(sum(r.hours_125 for r in new_rows), 2)
        header.hours_150 = round(sum(r.hours_150 for r in new_rows), 2)

        return result
