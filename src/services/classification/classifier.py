"""Report type classifier based on keyword signals in extracted text."""
from __future__ import annotations

import logging
import re

from src.domain.enums import ReportType

logger = logging.getLogger(__name__)

# Hard Type A signal: document title unique to this form type.
# כרטיס עובד / כרטיסי עובד appears at the top of every Type A sheet.
_TYPE_A_HARD = [
    r"כרטיס.?\s*עובד",   # "כרטיס עובד לחודש" / "כרטיסי עובד לחודש"
]

# Hard Type B signals: percentage columns that never appear in Type A.
_TYPE_B_HARD = [
    r"שעות\s+100%",          # column "שעות 100%"
    r"שעות\s+1[0-9][0-9]%",  # שעות 120% / 125% / 150% etc.
    r"שבת\s+150%",            # "שבת 150%" row/column
]

# Softer corroborating signals for Type B (scored).
_TYPE_B_SIGNALS = [
    r"שעות\s+נוספות",   # "overtime hours" title
    r"הפסקה",            # "break" column
]

# Softer corroborating signals for Type A (scored).
# Patterns are kept short so OCR noise or RTL reordering doesn't break them.
_TYPE_A_SIGNALS = [
    r"דוח\s+נוכחות\s+חודשי",   # report title (alternative heading)
    r"ימי\s+עבודה",              # "work days" — unique to Type A summary
    r"שעות\s+חודשי",             # "monthly hours" — unique to Type A summary
    r"מחיר\s*לשעה",              # "price per hour"
    r"לתשלום",                   # "to pay" — Type A footer field
]


def _count_matches(patterns: list[str], text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text))


class Classifier:
    """Classifies a report as Type A, Type B, or Unknown."""

    def classify(self, extracted_text: str) -> ReportType:
        # Hard check — Type A title takes absolute priority
        if _count_matches(_TYPE_A_HARD, extracted_text) > 0:
            logger.debug("Classifier: hard Type-A signal matched (כרטיס עובד).")
            return ReportType.TYPE_A

        # Hard check — Type B percentage columns
        if _count_matches(_TYPE_B_HARD, extracted_text) > 0:
            logger.debug("Classifier: hard Type-B signal matched (שעות %%%).")
            return ReportType.TYPE_B

        score_b = _count_matches(_TYPE_B_SIGNALS, extracted_text)
        score_a = _count_matches(_TYPE_A_SIGNALS, extracted_text)

        logger.debug("Classifier scores — A: %d, B: %d", score_a, score_b)

        if score_b > score_a:
            return ReportType.TYPE_B
        if score_a > 0:  # tie or A-wins → prefer A (conservative)
            return ReportType.TYPE_A

        # Fallback heuristic: look at column count
        lines = [l for l in extracted_text.splitlines() if "|" in l]
        if lines:
            avg_cols = sum(l.count("|") for l in lines) / len(lines)
            # Type B has ~10 columns (many pipes), Type A has ~6
            if avg_cols >= 8:
                logger.info("Fallback: classified as TYPE_B by column count.")
                return ReportType.TYPE_B
            if avg_cols >= 4:
                logger.info("Fallback: classified as TYPE_A by column count.")
                return ReportType.TYPE_A

        logger.warning("Could not classify report — returning UNKNOWN.")
        return ReportType.UNKNOWN
