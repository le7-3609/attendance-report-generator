"""Centralised transformation rules — single source of truth.

All numeric constants used by the variators live here as frozen dataclasses.
Changing a rule requires editing exactly one file.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class TypeAVariationRules:
    """Business rules for varying Type A (short-shift) reports."""

    min_entry: time = time(7, 0)
    max_entry: time = time(10, 0)
    min_shift_hours: float = 2.0
    max_shift_hours: float = 5.0
    entry_delta_minutes: int = 15
    exit_delta_minutes: int = 10
    # Fallback hourly rate range (₪) when OCR did not extract one
    fallback_rate_min: float = 33.0
    fallback_rate_max: float = 65.0


@dataclass(frozen=True)
class TypeBVariationRules:
    """Business rules for varying Type B (overtime-tier) reports."""

    entry_delta_minutes: int = 10
    exit_delta_minutes: int = 10
    min_shift_hours: float = 1.0
    max_shift_hours: float = 16.0
    # Israeli standard: 8 h regular, next 2 h at 125%, remainder at 150%
    regular_threshold_hours: float = 8.0
    ot_125_hours: float = 2.0
    # Probability that a weekday row gets a long (>10.5 h) shift
    long_shift_probability: float = 0.15
    long_shift_min_hours: float = 10.5
    long_shift_max_hours: float = 12.0
    # Break variation range in minutes
    break_delta_minutes: int = 5
    # Synthesised break range when no real break was recorded
    synthesised_break_min_minutes: int = 20
    synthesised_break_max_minutes: int = 45


TYPE_A_RULES = TypeAVariationRules()
TYPE_B_RULES = TypeBVariationRules()
