"""Normalize hour tokens coming from OCR/parsers.

Many attendance reports encode hours like HH.MM where the part after the dot is
*minutes* (base-60), not decimal (base-100). Example: 7.30 means 7 hours 30 min.

This helper converts such tokens to true decimal hours (base-60) when safe.
"""
from __future__ import annotations


def normalize_hours_token(raw: str) -> float:
    s = (raw or "").strip()
    if not s:
        return 0.0

    try:
        v = float(s)
    except ValueError:
        return 0.0

    if v < 0:
        return v

    # Only consider conversion when it looks like it has 1–2 decimal digits.
    if "." not in s:
        return v
    whole, frac = s.split(".", 1)
    if not frac or len(frac) > 2:
        return v
    if not whole.isdigit() or not frac.isdigit():
        return v

    minutes = int(frac.ljust(2, "0"))  # "7.3" -> 30 minutes
    hours = int(whole)

    # Some OCRs produce "7.70" meaning 7h70m. Treat 00–99 as minutes and carry.
    # If you actually want decimal hours, reports typically use 1–2 digits but
    # the minute-style encoding is far more common in attendance exports.
    if 0 <= minutes <= 99:
        hours += minutes // 60
        minutes = minutes % 60
        return round(hours + (minutes / 60.0), 2)

    return v

