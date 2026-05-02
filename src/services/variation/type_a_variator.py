"""Type A variation logic — adjusts entry/exit times within business rules."""
from __future__ import annotations

import dataclasses
import logging
import random
import time
from datetime import time as dtime
from collections.abc import Sequence

from src.config.rules import TYPE_A_RULES, TypeAVariationRules
from src.constants import HEB_WEEKDAYS as _HEB_WEEKDAYS
from src.domain.exceptions import TransformationError
from src.domain.models import AttendanceRow, ReportData, TypeAHeader
from src.services.variation.base_variator import BaseVariator
from src.services.variation.time_utils import add_minutes, hours_between

logger = logging.getLogger(__name__)


def _clamp_time(t: dtime, lo: dtime, hi: dtime) -> dtime:
    if t < lo:
        return lo
    if t > hi:
        return hi
    return t


class TypeAVariator(BaseVariator):
    """Applies realistic random variations to a Type A report."""

    def __init__(self, rules: TypeAVariationRules = TYPE_A_RULES, *, run_salt: int | None = None) -> None:
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
            entry_time = _clamp_time(dtime(8, rng.randint(0, 30)), rules.min_entry, rules.max_entry)
            exit_time = add_minutes(entry_time, int(rules.min_shift_hours * 60))

        original_duration_h = hours_between(entry_time, exit_time)

        delta_entry = rng.randint(-rules.entry_delta_minutes, rules.entry_delta_minutes)
        new_entry = _clamp_time(add_minutes(entry_time, delta_entry), rules.min_entry, rules.max_entry)

        target_duration_h = max(
            rules.min_shift_hours,
            min(rules.max_shift_hours, original_duration_h + rng.uniform(-0.25, 0.25)),
        )
        delta_exit = rng.randint(-rules.exit_delta_minutes, rules.exit_delta_minutes)
        raw_exit = add_minutes(new_entry, int(target_duration_h * 60) + delta_exit)

        actual_h = hours_between(new_entry, raw_exit)
        if actual_h < rules.min_shift_hours:
            raw_exit = add_minutes(new_entry, int(rules.min_shift_hours * 60))
        elif actual_h > rules.max_shift_hours:
            raw_exit = add_minutes(new_entry, int(rules.max_shift_hours * 60))

        new_total_hours = hours_between(new_entry, raw_exit)
        if new_total_hours <= 0:
            raise TransformationError(
                f"Variation produced non-positive hours for row {row.date}: {new_total_hours}"
            )

        return dataclasses.replace(
            row,
            entry_time=new_entry,
            exit_time=raw_exit,
            total_hours=new_total_hours,
            weekday=_HEB_WEEKDAYS.get(row.date.weekday(), ""),
        )

    def finalize(self, data: ReportData, rows: Sequence[AttendanceRow]) -> ReportData:
        rules = self._rules
        new_rows = [r for r in rows if r.date is not None]

        old_header: TypeAHeader = data.header  # type: ignore[assignment]
        total_hours = round(sum(r.total_hours for r in new_rows), 2)

        if old_header.hourly_rate:
            hourly_rate = old_header.hourly_rate
        else:
            rate_rng = random.Random(self._run_salt ^ (hash(old_header.month_label) & 0xFFFFFFFF))
            hourly_rate = round(rate_rng.uniform(rules.fallback_rate_min, rules.fallback_rate_max), 2)

        new_header = dataclasses.replace(
            old_header,
            work_days=len(new_rows),
            total_hours=total_hours,
            hourly_rate=hourly_rate,
            total_pay=round(total_hours * hourly_rate, 2),
        )
        return dataclasses.replace(data, header=new_header, rows=tuple(new_rows))
