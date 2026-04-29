"""Type A variation logic — adjusts entry/exit times within business rules."""
from __future__ import annotations

import dataclasses
import logging
import random
from datetime import datetime, time, timedelta

from src.config.rules import TYPE_A_RULES, TypeAVariationRules
from src.constants import HEB_WEEKDAYS as _HEB_WEEKDAYS
from src.domain.exceptions import TransformationError
from src.domain.models import AttendanceRow, ReportData, TypeAHeader
from src.services.variation.base_variator import BaseVariator

logger = logging.getLogger(__name__)


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

    def __init__(self, rules: TypeAVariationRules = TYPE_A_RULES) -> None:
        self._rules = rules

    def vary(self, data: ReportData) -> ReportData:
        rules = self._rules
        new_rows: list[AttendanceRow] = []

        for row in data.rows:
            if row.date is None:
                continue

            # Per-row deterministic RNG — seeded from the row's date so the
            # same input always produces the same output, independent of call order.
            d = row.date
            rng = random.Random(d.year * 10000 + d.month * 100 + d.day)

            entry_time = row.entry_time
            exit_time = row.exit_time

            # If OCR failed to extract times, synthesise plausible ones
            if entry_time is None or exit_time is None:
                logger.debug("Synthesising times for incomplete row (date=%s).", row.date)
                entry_time = _clamp_time(
                    time(8, rng.randint(0, 30)), rules.min_entry, rules.max_entry
                )
                exit_time = _add_minutes(entry_time, int(rules.min_shift_hours * 60))

            original_duration_h = _hours_between(entry_time, exit_time)

            # Adjust entry time
            delta_entry = rng.randint(-rules.entry_delta_minutes, rules.entry_delta_minutes)
            new_entry = _clamp_time(_add_minutes(entry_time, delta_entry), rules.min_entry, rules.max_entry)

            # Adjust shift duration within valid range
            target_duration_h = max(
                rules.min_shift_hours,
                min(rules.max_shift_hours, original_duration_h + rng.uniform(-0.25, 0.25)),
            )
            delta_exit = rng.randint(-rules.exit_delta_minutes, rules.exit_delta_minutes)
            raw_exit = _add_minutes(new_entry, int(target_duration_h * 60) + delta_exit)

            # Enforce exit > entry and total hours within valid range
            actual_h = _hours_between(new_entry, raw_exit)
            if actual_h < rules.min_shift_hours:
                raw_exit = _add_minutes(new_entry, int(rules.min_shift_hours * 60))
            elif actual_h > rules.max_shift_hours:
                raw_exit = _add_minutes(new_entry, int(rules.max_shift_hours * 60))

            new_total_hours = _hours_between(new_entry, raw_exit)
            if new_total_hours <= 0:
                raise TransformationError(
                    f"Variation produced non-positive hours for row {row.date}: {new_total_hours}"
                )

            # Build a new immutable row — the original is never modified
            new_rows.append(dataclasses.replace(
                row,
                entry_time=new_entry,
                exit_time=raw_exit,
                total_hours=new_total_hours,
                # Recalculate weekday from the actual date (fixes OCR errors)
                weekday=_HEB_WEEKDAYS.get(row.date.weekday(), ""),
            ))

        # Recalculate header totals
        old_header: TypeAHeader = data.header  # type: ignore[assignment]
        total_hours = round(sum(r.total_hours for r in new_rows), 2)

        # If OCR did not extract an hourly rate, synthesise a plausible one.
        # Seed from month_label so the fallback is also deterministic.
        if old_header.hourly_rate:
            hourly_rate = old_header.hourly_rate
        else:
            rate_rng = random.Random(hash(old_header.month_label) & 0xFFFFFFFF)
            hourly_rate = round(
                rate_rng.uniform(rules.fallback_rate_min, rules.fallback_rate_max), 2
            )

        new_header = dataclasses.replace(
            old_header,
            work_days=len(new_rows),
            total_hours=total_hours,
            hourly_rate=hourly_rate,
            total_pay=round(total_hours * hourly_rate, 2),
        )
        return dataclasses.replace(data, header=new_header, rows=tuple(new_rows))
