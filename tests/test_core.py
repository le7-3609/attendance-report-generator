"""Basic smoke tests — run with: uv run pytest"""
from __future__ import annotations

from datetime import date, time

import pytest

from src.domain.enums import ReportType
from src.domain.models import AttendanceRow, ReportData, TypeAHeader, TypeBHeader
from src.services.classification.classifier import Classifier
from src.services.rendering.type_a_renderer import TypeARenderer
from src.services.rendering.type_b_renderer import TypeBRenderer
from src.services.variation.type_a_variator import TypeAVariator
from src.services.variation.type_b_variator import TypeBVariator


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class TestClassifier:
    def setup_method(self):
        self.clf = Classifier()

    def test_classifies_type_a(self):
        text = "דוח נוכחות חודשי\nמחיר לשעה: 32\nסה\"כ לתשלום: 800"
        assert self.clf.classify(text) == ReportType.TYPE_A

    def test_classifies_type_b(self):
        text = "נ.ע. הנשר בע\"מ\nדוח נוכחות מפורט עם שעות נוספות\n125% | 150%\nהפסקה"
        assert self.clf.classify(text) == ReportType.TYPE_B

    def test_unknown(self):
        assert self.clf.classify("random text without signals") == ReportType.UNKNOWN


# ---------------------------------------------------------------------------
# Type A variator
# ---------------------------------------------------------------------------

def _make_type_a_data() -> ReportData:
    rows = [
        AttendanceRow(
            date=date(2023, 1, 4),
            weekday="רביעי",
            entry_time=time(8, 4),
            exit_time=time(10, 45),
            total_hours=2.68,
        ),
        AttendanceRow(
            date=date(2023, 1, 17),
            weekday="שלישי",
            entry_time=time(7, 49),
            exit_time=time(11, 7),
            total_hours=3.30,
        ),
    ]
    header = TypeAHeader(
        work_days=2, total_hours=5.98, hourly_rate=32.0, total_pay=191.36
    )
    return ReportData(report_type=ReportType.TYPE_A, header=header, rows=tuple(rows))


class TestTypeAVariator:
    def test_exit_after_entry(self):
        variator = TypeAVariator()
        for _ in range(20):  # run multiple times since random
            result = variator.vary(_make_type_a_data())
            for row in result.rows:
                assert row.exit_time > row.entry_time, (
                    f"exit {row.exit_time} not after entry {row.entry_time}"
                )

    def test_hours_match_times(self):
        variator = TypeAVariator()
        result = variator.vary(_make_type_a_data())
        for row in result.rows:
            from datetime import datetime
            dt1 = datetime(2000, 1, 1, row.entry_time.hour, row.entry_time.minute)
            dt2 = datetime(2000, 1, 1, row.exit_time.hour, row.exit_time.minute)
            expected = round((dt2 - dt1).total_seconds() / 3600, 2)
            assert abs(row.total_hours - expected) < 0.01

    def test_summary_totals_recalculated(self):
        variator = TypeAVariator()
        result = variator.vary(_make_type_a_data())
        expected_total = round(sum(r.total_hours for r in result.rows), 2)
        assert result.header.total_hours == expected_total  # type: ignore[union-attr]

    def test_weekday_corrected(self):
        variator = TypeAVariator()
        result = variator.vary(_make_type_a_data())
        # date(2023, 1, 4) is a Wednesday → "רביעי"
        assert result.rows[0].weekday == "רביעי"


# ---------------------------------------------------------------------------
# Type B variator
# ---------------------------------------------------------------------------

def _make_type_b_data() -> ReportData:
    rows = [
        AttendanceRow(
            date=date(2023, 2, 16),
            weekday="חמישי",
            entry_time=time(0, 31),
            exit_time=time(17, 16),
            break_time=time(1, 0),
            total_hours=15.75,
            hours_100=8.0,
            hours_125=1.0,
            hours_150=6.75,
        ),
    ]
    header = TypeBHeader(work_days=1, total_hours=15.75, hours_100=8.0, hours_125=1.0, hours_150=6.75)
    return ReportData(report_type=ReportType.TYPE_B, header=header, rows=tuple(rows))


class TestTypeBVariator:
    def test_overtime_tiers_sum_to_total(self):
        variator = TypeBVariator()
        for _ in range(20):
            result = variator.vary(_make_type_b_data())
            for row in result.rows:
                tier_sum = round(row.hours_100 + row.hours_125 + row.hours_150, 2)
                assert abs(tier_sum - row.total_hours) < 0.02, (
                    f"tiers {tier_sum} != total {row.total_hours}"
                )

    def test_exit_after_entry(self):
        variator = TypeBVariator()
        for _ in range(20):
            result = variator.vary(_make_type_b_data())
            for row in result.rows:
                assert row.exit_time > row.entry_time


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

class TestTypeARenderer:
    def test_renders_html(self):
        renderer = TypeARenderer()
        html = renderer.render(_make_type_a_data())
        assert "<html" in html.lower() or "<!doctype" in html.lower() or "<table" in html.lower()

    def test_contains_date(self):
        renderer = TypeARenderer()
        html = renderer.render(_make_type_a_data())
        # date(2023, 1, 4) should appear in some form
        assert "2023" in html

    def test_contains_entry_time(self):
        renderer = TypeARenderer()
        html = renderer.render(_make_type_a_data())
        assert "08:04" in html


class TestTypeBRenderer:
    def test_renders_html(self):
        renderer = TypeBRenderer()
        html = renderer.render(_make_type_b_data())
        assert "<html" in html.lower() or "<!doctype" in html.lower() or "<table" in html.lower()

    def test_contains_overtime_hours(self):
        renderer = TypeBRenderer()
        html = renderer.render(_make_type_b_data())
        # hours_100 = 8.0 should appear somewhere
        assert "8" in html


# ---------------------------------------------------------------------------
# Integration: full round-trip parse-data → vary → render → PDF bytes
# ---------------------------------------------------------------------------

class TestIntegrationTypeA:
    """Vary → render → PDF for a Type A report (no real PDF input needed)."""

    def test_vary_render_produces_html(self):
        data = _make_type_a_data()
        varied = TypeAVariator().vary(data)
        html = TypeARenderer().render(varied)
        assert isinstance(html, str)
        assert len(html) > 100

    def test_vary_then_pdf_bytes(self):
        from src.services.pdf_service import PdfService
        data = _make_type_a_data()
        varied = TypeAVariator().vary(data)
        pdf_bytes = PdfService().generate(varied)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"


class TestIntegrationTypeB:
    """Vary → render → PDF for a Type B report (no real PDF input needed)."""

    def test_vary_render_produces_html(self):
        data = _make_type_b_data()
        varied = TypeBVariator().vary(data)
        html = TypeBRenderer().render(varied)
        assert isinstance(html, str)
        assert len(html) > 100

    def test_vary_then_pdf_bytes(self):
        from src.services.pdf_service import PdfService
        data = _make_type_b_data()
        varied = TypeBVariator().vary(data)
        pdf_bytes = PdfService().generate(varied)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Seed reproducibility
# ---------------------------------------------------------------------------

class TestSeedReproducibility:
    def test_type_a_same_input_gives_same_result(self):
        """Per-row seeding from date means same input → same output, always."""
        data = _make_type_a_data()
        r1 = TypeAVariator().vary(data)
        r2 = TypeAVariator().vary(data)
        assert r1.rows[0].entry_time == r2.rows[0].entry_time
        assert r1.rows[0].exit_time == r2.rows[0].exit_time

    def test_type_b_same_input_gives_same_result(self):
        data = _make_type_b_data()
        r1 = TypeBVariator().vary(data)
        r2 = TypeBVariator().vary(data)
        assert r1.rows[0].entry_time == r2.rows[0].entry_time
        assert r1.rows[0].exit_time == r2.rows[0].exit_time
