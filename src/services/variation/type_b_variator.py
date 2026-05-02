"""Type B variation logic — adjusts times and recalculates overtime tiers."""
from __future__ import annotations

import dataclasses
import logging
import random
import time
from datetime import time as dtime
from collections.abc import Sequence

from src.config.rules import TYPE_B_RULES, TypeBVariationRules
from src.constants import HEB_WEEKDAYS as _HEB_WEEKDAYS
from src.domain.exceptions import TransformationError
from src.domain.models import AttendanceRow, ReportData, TypeBHeader
from src.services.variation.base_variator import BaseVariator
from src.services.variation.time_utils import add_minutes, hours_between

logger = logging.getLogger(__name__)

_DEFAULT_LOCATIONS = [
    "תל אביב", "ירושלים", "חיפה", "ראשון לציון",
    "פתח תקווה", "אשדוד", "נתניה", "באר שבע",
]


def _split_overtime(
    net_hours: float,
    regular_threshold: float,
    ot_125_hours: float,
) -> tuple[float, float, float]:
    """Split net working hours into 100% / 125% / 150% tiers."""
    h100 = min(net_hours, regular_threshold)
    h125 = min(max(net_hours - regular_threshold, 0.0), ot_125_hours)
    h150 = max(net_hours - regular_threshold - ot_125_hours, 0.0)
    return round(h100, 2), round(h125, 2), round(h150, 2)


class TypeBVariator(BaseVariator):
    """Applies realistic random variations to a Type B report."""

    def __init__(self, rules: TypeBVariationRules = TYPE_B_RULES, *, run_salt: int | None = None) -> None:
        self._rules = rules
        self._run_salt = run_salt if run_salt is not None else time.time_ns() ^ random.getrandbits(32)

    def transform_row(self, row: AttendanceRow) -> AttendanceRow:
        if row.date is None:
            return row

        rules = self._rules
        d = row.date
        rng = random.Random(self._run_salt ^ (d.year * 10000 + d.month * 100 + d.day))

        entry_time = row.entry_time
        exit_time = row.exit_time

        if entry_time is None or exit_time is None:
            logger.debug("Synthesising times for incomplete row (date=%s).", row.date)
            entry_time = dtime(8, rng.randint(0, 30))
            if rng.random() < 0.20:
                exit_time = dtime(rng.randint(19, 20), rng.randint(0, 59))
            else:
                exit_time = dtime(rng.randint(16, 18), rng.randint(0, 59))

        original_gross_h = hours_between(entry_time, exit_time)

        delta_entry = rng.randint(-rules.entry_delta_minutes, rules.entry_delta_minutes)
        new_entry = add_minutes(entry_time, delta_entry)

        delta_exit = rng.randint(-rules.exit_delta_minutes, rules.exit_delta_minutes)
        target_gross_minutes = int(original_gross_h * 60) + delta_exit

        if rng.random() < rules.long_shift_probability and row.date.weekday() != 5:
            target_gross_minutes = rng.randint(
                int(rules.long_shift_min_hours * 60),
                int(rules.long_shift_max_hours * 60),
            )

        target_gross_minutes = max(int(rules.min_shift_hours * 60), target_gross_minutes)
        target_gross_minutes = min(int(rules.max_shift_hours * 60), target_gross_minutes)
        new_exit = add_minutes(new_entry, target_gross_minutes)

        has_real_break = (
            row.break_time is not None and (row.break_time.hour > 0 or row.break_time.minute > 0)
        )
        if has_real_break:
            break_delta = rng.randint(-rules.break_delta_minutes, rules.break_delta_minutes)
            new_break_minutes = max(
                1,
                min(1439, row.break_time.hour * 60 + row.break_time.minute + break_delta),  # type: ignore[union-attr]
            )
            new_break_time = dtime(new_break_minutes // 60, new_break_minutes % 60)
            break_h = new_break_minutes / 60.0
        else:
            break_minutes = rng.randint(
                rules.synthesised_break_min_minutes,
                rules.synthesised_break_max_minutes,
            )
            new_break_time = dtime(0, break_minutes)
            break_h = break_minutes / 60.0

        net_h = round(hours_between(new_entry, new_exit) - break_h, 2)
        net_h = max(0.0, net_h)

        if net_h <= 0:
            raise TransformationError(
                f"Variation produced non-positive net hours for row {row.date}: {net_h}"
            )

        h100, h125, h150 = _split_overtime(net_h, rules.regular_threshold_hours, rules.ot_125_hours)

        location = row.location or rng.choice(_DEFAULT_LOCATIONS)

        return dataclasses.replace(
            row,
            entry_time=new_entry,
            exit_time=new_exit,
            break_time=new_break_time,
            total_hours=net_h,
            hours_100=h100,
            hours_125=h125,
            hours_150=h150,
            location=location,
            weekday=_HEB_WEEKDAYS.get(row.date.weekday(), ""),
            is_sabbath=row.date.weekday() == 5,
        )

    def finalize(self, data: ReportData, rows: Sequence[AttendanceRow]) -> ReportData:
        new_rows = [r for r in rows if r.date is not None]

        old_header: TypeBHeader = data.header  # type: ignore[assignment]
        new_header = dataclasses.replace(
            old_header,
            work_days=sum(1 for r in new_rows if not bool(r.is_sabbath)),
            total_hours=round(sum(r.total_hours for r in new_rows), 2),
            hours_100=round(sum((r.hours_100 or 0.0) for r in new_rows), 2),
            hours_125=round(sum((r.hours_125 or 0.0) for r in new_rows), 2),
            hours_150=round(sum((r.hours_150 or 0.0) for r in new_rows), 2),
        )
        return dataclasses.replace(data, header=new_header, rows=tuple(new_rows))
