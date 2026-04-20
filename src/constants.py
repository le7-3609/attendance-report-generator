"""Shared constants used across parsers, variators, and other services.

Centralising these here prevents the values from drifting out of sync when
the same constant was previously defined in multiple files.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Hebrew weekday names keyed by Python's date.weekday() (Monday=0, Sunday=6)
# ---------------------------------------------------------------------------
HEB_WEEKDAYS: dict[int, str] = {
    0: "שני",
    1: "שלישי",
    2: "רביעי",
    3: "חמישי",
    4: "שישי",
    5: "שבת",
    6: "ראשון",
}

# Set of weekday name strings — useful for membership tests inside parsers.
HEB_WEEKDAY_NAMES: frozenset[str] = frozenset(HEB_WEEKDAYS.values())

# ---------------------------------------------------------------------------
# Hebrew month names keyed by month number (1–12)
# ---------------------------------------------------------------------------
HEB_MONTHS: dict[int, str] = {
    1: "ינואר",   2: "פברואר",  3: "מרץ",     4: "אפריל",
    5: "מאי",     6: "יוני",    7: "יולי",    8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}

# ---------------------------------------------------------------------------
# Common regex patterns shared across parsers
# ---------------------------------------------------------------------------

# Date: DD/MM/YY or DD/MM/YYYY (single-digit D or M allowed)
DATE_RE = re.compile(r"\b(\d{1,2})[/\\|.\-](\d{1,2})[/\\|.\-](\d{2,4})\b")

# Time: H:MM or HH:MM
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")

# Decimal (float) hours
FLOAT_RE = re.compile(r"\b(\d+\.\d+)\b")
