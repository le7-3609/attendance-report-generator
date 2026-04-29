"""Validation/audit decorator for transformation strategies.

This layer enforces invariants on the output of a variation strategy.
It centralizes "trust but verify" checks so the rest of the pipeline can
assume ReportData is internally consistent.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from src.domain.enums import ReportType
from src.domain.exceptions import TransformationError
from src.domain.models import AttendanceRow, ReportData, TypeAHeader, TypeBHeader
from src.services.variation.base_variator import BaseVariator
from src.services.variation.base_strategy import BaseTransformationStrategy


def _hours_between(t1: time, t2: time) -> float:
    """Hours between times; supports crossing midnight."""
    dt1 = datetime(2000, 1, 1, t1.hour, t1.minute)
    dt2 = datetime(2000, 1, 1, t2.hour, t2.minute)
    if dt2 <= dt1:
        dt2 += timedelta(days=1)
    return round((dt2 - dt1).total_seconds() / 3600, 2)


class ValidatingVariatorDecorator(BaseVariator, BaseTransformationStrategy):
    """Wraps a strategy/variator and audits its output for consistency."""

    def __init__(
        self,
        inner: BaseVariator | BaseTransformationStrategy,
        *,
        max_hours_error: float = 0.03,
    ) -> None:
        self._inner = inner
        self._max_hours_error = max_hours_error

    def vary(self, data: ReportData) -> ReportData:
        if not isinstance(self._inner, BaseVariator):
            raise TypeError("Inner object does not implement BaseVariator.")
        out = self._inner.vary(data)
        self._audit(out)
        return out

    def transform_row(self, row: AttendanceRow) -> AttendanceRow:
        if not isinstance(self._inner, BaseTransformationStrategy):
            raise TypeError("Inner object does not implement BaseTransformationStrategy.")
        out = self._inner.transform_row(row)
        self._audit_row(-1, out)
        return out

    def finalize(self, data: ReportData, rows: list[AttendanceRow] | tuple[AttendanceRow, ...]) -> ReportData:
        if not isinstance(self._inner, BaseTransformationStrategy):
            raise TypeError("Inner object does not implement BaseTransformationStrategy.")
        out = self._inner.finalize(data, rows)
        self._audit(out)
        return out

    # --------------------------------------------------------------------- #
    def _audit(self, data: ReportData) -> None:
        if data.report_type == ReportType.UNKNOWN:
            raise TransformationError("Validation failed: report_type is UNKNOWN.")

        if data.rows is None:
            raise TransformationError("Validation failed: rows is None.")

        for idx, row in enumerate(data.rows):
            self._audit_row(idx, row)

        if data.report_type == ReportType.TYPE_A:
            self._audit_type_a(data)
        elif data.report_type == ReportType.TYPE_B:
            self._audit_type_b(data)

    def _audit_row(self, idx: int, row: AttendanceRow) -> None:
        if row.date is None:
            raise TransformationError(f"Validation failed: row[{idx}] missing date.")

        if row.entry_time is None or row.exit_time is None:
            raise TransformationError(
                f"Validation failed: row[{idx}] missing entry/exit time."
            )

        if row.exit_time == row.entry_time:
            raise TransformationError(
                f"Validation failed: row[{idx}] exit_time equals entry_time."
            )

        expected_total = _hours_between(row.entry_time, row.exit_time)

        is_type_bish = (
            row.break_time is not None
            or row.hours_100 is not None
            or row.hours_125 is not None
            or row.hours_150 is not None
            or row.is_sabbath is not None
        )
        if is_type_bish:
            break_h = 0.0
            if row.break_time and (row.break_time.hour > 0 or row.break_time.minute > 0):
                break_h = (row.break_time.hour * 60 + row.break_time.minute) / 60.0
            expected_total = round(max(0.0, expected_total - break_h), 2)

        if abs(row.total_hours - expected_total) > self._max_hours_error:
            raise TransformationError(
                f"Validation failed: row[{idx}] total_hours mismatch "
                f"(got={row.total_hours:.2f}, expected≈{expected_total:.2f})."
            )

        if row.total_hours <= 0:
            raise TransformationError(
                f"Validation failed: row[{idx}] non-positive total_hours={row.total_hours}."
            )

        if is_type_bish:
            if row.is_sabbath is None:
                raise TransformationError(f"Validation failed: row[{idx}] missing is_sabbath for Type B.")

            tier_sum = round((row.hours_100 or 0.0) + (row.hours_125 or 0.0) + (row.hours_150 or 0.0), 2)
            if abs(tier_sum - row.total_hours) > 0.05:
                raise TransformationError(
                    f"Validation failed: row[{idx}] overtime tiers do not sum to total "
                    f"(tiers={tier_sum:.2f}, total={row.total_hours:.2f})."
                )

            # Optional but useful: sabbath flag must match the date.
            if bool(row.is_sabbath) != (row.date.weekday() == 5):
                raise TransformationError(
                    f"Validation failed: row[{idx}] is_sabbath inconsistent with date."
                )

    def _audit_type_a(self, data: ReportData) -> None:
        header: TypeAHeader = data.header  # type: ignore[assignment]
        expected_total = round(sum(r.total_hours for r in data.rows), 2)
        if abs(header.total_hours - expected_total) > 0.05:
            raise TransformationError(
                "Validation failed: Type A header total_hours mismatch "
                f"(got={header.total_hours:.2f}, expected={expected_total:.2f})."
            )
        if header.work_days != len(data.rows):
            raise TransformationError(
                "Validation failed: Type A header work_days mismatch "
                f"(got={header.work_days}, expected={len(data.rows)})."
            )

    def _audit_type_b(self, data: ReportData) -> None:
        header: TypeBHeader = data.header  # type: ignore[assignment]
        expected_total = round(sum(r.total_hours for r in data.rows), 2)
        expected_100 = round(sum((r.hours_100 or 0.0) for r in data.rows), 2)
        expected_125 = round(sum((r.hours_125 or 0.0) for r in data.rows), 2)
        expected_150 = round(sum((r.hours_150 or 0.0) for r in data.rows), 2)
        expected_work_days = sum(1 for r in data.rows if not bool(r.is_sabbath))

        if abs(header.total_hours - expected_total) > 0.05:
            raise TransformationError(
                "Validation failed: Type B header total_hours mismatch "
                f"(got={header.total_hours:.2f}, expected={expected_total:.2f})."
            )
        if abs(header.hours_100 - expected_100) > 0.05:
            raise TransformationError(
                "Validation failed: Type B header hours_100 mismatch "
                f"(got={header.hours_100:.2f}, expected={expected_100:.2f})."
            )
        if abs(header.hours_125 - expected_125) > 0.05:
            raise TransformationError(
                "Validation failed: Type B header hours_125 mismatch "
                f"(got={header.hours_125:.2f}, expected={expected_125:.2f})."
            )
        if abs(header.hours_150 - expected_150) > 0.05:
            raise TransformationError(
                "Validation failed: Type B header hours_150 mismatch "
                f"(got={header.hours_150:.2f}, expected={expected_150:.2f})."
            )
        if header.work_days != expected_work_days:
            raise TransformationError(
                "Validation failed: Type B header work_days mismatch "
                f"(got={header.work_days}, expected={expected_work_days})."
            )

