"""Shared time arithmetic utilities for variation strategies."""
from __future__ import annotations

from datetime import datetime, time, timedelta


def add_minutes(t: time, minutes: int) -> time:
    dt = datetime(2000, 1, 2, t.hour, t.minute) + timedelta(minutes=minutes)
    return dt.time()


def hours_between(t1: time, t2: time) -> float:
    """Hours between two times; supports crossing midnight."""
    dt1 = datetime(2000, 1, 2, t1.hour, t1.minute)
    dt2 = datetime(2000, 1, 2, t2.hour, t2.minute)
    if dt2 <= dt1:
        dt2 += timedelta(days=1)
    return round((dt2 - dt1).total_seconds() / 3600, 2)
