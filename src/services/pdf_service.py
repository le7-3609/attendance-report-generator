"""PDF generation service using ReportLab — no browser required."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path

from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from src.domain.enums import ReportType
from src.domain.models import ReportData, TypeAHeader, TypeBHeader

logger = logging.getLogger(__name__)

# Locate the bundled Hebrew font.
# 1. Project-relative path works in development (python -m src.main …).
# 2. An env-var override (ATTENDANCE_FONTS_DIR) makes it work when the
#    package is installed to a different location (e.g. pip install .).
def _find_font_path() -> Path:
    env_dir = os.environ.get("ATTENDANCE_FONTS_DIR")
    if env_dir:
        candidate = Path(env_dir) / "NotoSansHebrew-Regular.ttf"
        if candidate.exists():
            return candidate
    # Default: fonts/ at the project root, resolved from this file's location.
    return Path(__file__).resolve().parent.parent.parent / "fonts" / "NotoSansHebrew-Regular.ttf"

_FONT_TTF  = _find_font_path()
_FONT_NAME = "NotoSansHebrew"

_GREY   = colors.HexColor("#E0E0E0")
_LIGHT  = colors.HexColor("#F9F9F9")
_PINK   = colors.HexColor("#FFE4E1")
_DARK   = colors.HexColor("#707070")
_BORDER = colors.HexColor("#BBBBBB")
_WHITE  = colors.white
_YELLOW_BG = colors.HexColor("#FFF8E1")
_ORANGE_BD = colors.HexColor("#F0C040")


def _disclaimer_elements(font: str) -> list:
    """Return a disclaimer box to append at the bottom of every generated PDF."""
    s = ParagraphStyle(
        "Disc", fontName=font, fontSize=8, leading=12, alignment=1,
        textColor=colors.HexColor("#7A5C00"),
        backColor=_YELLOW_BG,
        borderColor=_ORANGE_BD,
        borderWidth=1,
        borderPadding=6,
        spaceAfter=0,
    )
    line1 = _h("\u26a0 \u05de\u05e1\u05de\u05da \u05d6\u05d4 \u05e0\u05d5\u05e6\u05e8 \u05e2\u05dc-\u05d9\u05d3\u05d9 \u05de\u05d7\u05d5\u05dc\u05dc \u05d3\u05d5\u05d7\u05d5\u05ea \u05d4\u05e0\u05d5\u05db\u05d7\u05d5\u05ea \u05d4\u05d0\u05d5\u05d8\u05d5\u05de\u05d8\u05d9 \u05d5\u05d0\u05d9\u05e0\u05d5 \u05d3\u05d5\u05d7 \u05e0\u05d5\u05db\u05d7\u05d5\u05ea \u05d0\u05de\u05d9\u05ea\u05d9.")
    line2 = _h("\u05d4\u05e0\u05ea\u05d5\u05e0\u05d9\u05dd \u05d1\u05d5 \u05d4\u05d9\u05e0\u05dd \u05d4\u05d9\u05e4\u05d5\u05ea\u05d8\u05d9\u05d9\u05dd \u05d1\u05dc\u05d1\u05d3 \u05d5\u05d0\u05d9\u05df \u05dc\u05d4\u05e9\u05ea\u05de\u05e9 \u05d1\u05d5 \u05dc\u05db\u05dc \u05de\u05d8\u05e8\u05d4 \u05de\u05e9\u05e4\u05d8\u05d9\u05ea, \u05db\u05e1\u05e4\u05d9\u05ea \u05d0\u05d5 \u05d0\u05d7\u05e8\u05ea.")
    return [Spacer(1, 0.4*cm), Paragraph(f"{line1}<br/>{line2}", s)]


def _register_font() -> str:
    """Register the Hebrew font once and return the font name to use."""
    if _FONT_TTF.exists():
        if _FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT_TTF)))
        return _FONT_NAME
    logger.warning("Hebrew font not found at %s; falling back to Helvetica.", _FONT_TTF)
    return "Helvetica"


# Register at import time so generate() pays no overhead per call.
_REGISTERED_FONT: str = _register_font()


def _h(text: str) -> str:
    """Apply Unicode BiDi so Hebrew renders correctly in ReportLab."""
    return get_display(str(text))


def _fmt_time(t) -> str:
    return t.strftime("%H:%M") if t else ""


def _fmt_f(v: float) -> str:
    return f"{v:.2f}" if v else ""


class PdfService:
    """Converts ReportData directly to PDF bytes using ReportLab."""

    def generate(self, data: ReportData) -> bytes:
        font = _REGISTERED_FONT
        if data.report_type == ReportType.TYPE_A:
            return self._type_a(data, font)
        return self._type_b(data, font)

    # ── Type A ─────────────────────────────────────────────────────────────────
    # כרטיס עובד: portrait A4, flat hourly rate, summary at top

    def _type_a(self, data: ReportData, font: str) -> bytes:
        header: TypeAHeader = data.header  # type: ignore[assignment]
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm,   bottomMargin=1.5*cm,
        )
        s_title = ParagraphStyle("T", fontName=font, fontSize=14, leading=20,
                                 alignment=1, spaceAfter=4)
        s_sub   = ParagraphStyle("S", fontName=font, fontSize=11, leading=16,
                                 alignment=1, spaceAfter=4)
        elements = []

        elements.append(Paragraph(_h("דוח נוכחות חודשי"), s_title))
        if header.month_label:
            elements.append(Paragraph(_h(header.month_label), s_sub))
        elements.append(Spacer(1, 0.4*cm))

        # Summary box
        smry = [
            [_h("ימי עבודה לחודש:"),   str(header.work_days)],
            [_h('סה"כ שעות חודשיות:'), f"{header.total_hours:.2f}"],
            [_h("מחיר לשעה:"),
             f"\u20aa{header.hourly_rate:.2f}" if header.hourly_rate else ""],
            [_h('סה"כ לתשלום:'),
             f"\u20aa{header.total_pay:.2f}"   if header.total_pay    else ""],
        ]
        st = Table(smry, colWidths=[4.5*cm, 3.5*cm])
        st.setStyle(TableStyle([
            ("FONTNAME",      (0,0),(-1,-1), font),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
            ("ALIGN",         (0,0),(0,-1),  "RIGHT"),
            ("ALIGN",         (1,0),(1,-1),  "LEFT"),
            ("TEXTCOLOR",     (0,0),(0,-1),  colors.HexColor("#555555")),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("BOX",           (0,0),(-1,-1), 0.5, _BORDER),
            ("INNERGRID",     (0,0),(-1,-1), 0.5, _BORDER),
            ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#FAFAFA")),
        ]))
        elements.append(st)
        elements.append(Spacer(1, 0.5*cm))

        # Attendance table
        hdrs = ["הערות", 'סה"כ שעות', "שעת יציאה", "שעת כניסה", "יום בשבוע", "תאריך"]
        cws  = [3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        rows_data = [[_h(h) for h in hdrs]]
        for row in data.rows:
            rows_data.append([
                _h(row.notes),
                _fmt_f(row.total_hours),
                _fmt_time(row.exit_time),
                _fmt_time(row.entry_time),
                _h(row.weekday),
                row.date.strftime("%d/%m/%Y") if row.date else "",
            ])
        rows_data.append(["", f"{header.total_hours:.2f}", "", "", _h('סה"כ'), ""])

        n = len(rows_data)
        tbl = Table(rows_data, colWidths=cws, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME",        (0,0),(-1,-1), font),
            ("FONTSIZE",        (0,0),(-1,-1), 9),
            ("ALIGN",           (0,0),(-1,-1), "CENTER"),
            ("VALIGN",          (0,0),(-1,-1), "MIDDLE"),
            ("BACKGROUND",      (0,0),(-1,0),  _GREY),
            ("BACKGROUND",      (0,n-1),(-1,n-1), _GREY),
            ("BOX",             (0,0),(-1,-1), 0.5, _BORDER),
            ("INNERGRID",       (0,0),(-1,-1), 0.5, _BORDER),
            ("ROWBACKGROUNDS",  (0,1),(-1,n-2), [_WHITE, _LIGHT]),
        ]))
        elements.append(tbl)
        elements += _disclaimer_elements(font)
        doc.build(elements)
        return buf.getvalue()

    # ── Type B ─────────────────────────────────────────────────────────────────
    # נשר כח אדם: landscape A4, overtime tiers, summary at bottom

    def _type_b(self, data: ReportData, font: str) -> bytes:
        header: TypeBHeader = data.header  # type: ignore[assignment]
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            rightMargin=1.0*cm, leftMargin=1.0*cm,
            topMargin=1.2*cm,   bottomMargin=1.2*cm,
        )
        s_title = ParagraphStyle("T", fontName=font, fontSize=13, leading=18,
                                 alignment=1, spaceAfter=2)
        s_sub   = ParagraphStyle("S", fontName=font, fontSize=10, leading=15,
                                 alignment=1, spaceAfter=2)
        elements = []

        elements.append(Paragraph(_h(header.company), s_title))
        elements.append(Paragraph(_h("דוח נוכחות מפורט עם שעות נוספות"), s_sub))
        if header.month_label:
            elements.append(Paragraph(_h(header.month_label), s_sub))
        elements.append(Spacer(1, 0.3*cm))

        hdrs = ["150%","125%","100%",'סה"כ',"הפסקה","יציאה","כניסה","מקום","יום","תאריך"]
        cws  = [1.5*cm,1.5*cm,1.5*cm,1.7*cm,1.7*cm,1.9*cm,1.9*cm,2.8*cm,2.3*cm,2.5*cm]
        rows_data = [[_h(h) for h in hdrs]]
        for row in data.rows:
            rows_data.append([
                _fmt_f(row.hours_150),
                _fmt_f(row.hours_125),
                _fmt_f(row.hours_100),
                _fmt_f(row.total_hours),
                _fmt_time(row.break_time),
                _fmt_time(row.exit_time),
                _fmt_time(row.entry_time),
                _h(row.location),
                _h(row.weekday),
                row.date.strftime("%d/%m/%Y") if row.date else "",
            ])
        rows_data.append([
            f"{header.hours_150:.2f}", f"{header.hours_125:.2f}",
            f"{header.hours_100:.2f}", f"{header.total_hours:.2f}",
            "", "", "", "", _h('סה"כ'), "",
        ])

        sabbath_idxs = [i + 1 for i, row in enumerate(data.rows) if row.is_sabbath]
        n = len(rows_data)
        tbl = Table(rows_data, colWidths=cws, repeatRows=1)
        style_cmds = [
            ("FONTNAME",       (0,0),(-1,-1), font),
            ("FONTSIZE",       (0,0),(-1,-1), 8),
            ("ALIGN",          (0,0),(-1,-1), "CENTER"),
            ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
            ("BACKGROUND",     (0,0),(-1,0),  _GREY),
            ("BACKGROUND",     (0,n-1),(-1,n-1), _GREY),
            ("BOX",            (0,0),(-1,-1), 0.5, _BORDER),
            ("INNERGRID",      (0,0),(-1,-1), 0.5, _BORDER),
            ("ROWBACKGROUNDS", (0,1),(-1,n-2), [_WHITE, _LIGHT]),
        ]
        for si in sabbath_idxs:
            style_cmds.append(("BACKGROUND", (0, si), (-1, si), _PINK))
        tbl.setStyle(TableStyle(style_cmds))
        elements.append(tbl)
        elements.append(Spacer(1, 0.4*cm))

        # Summary mini-table
        smry = [
            [_h("ימי עבודה:"),   str(header.work_days)],
            [_h('סה"כ שעות:'),  f"{header.total_hours:.2f}"],
            [_h("שעות 100%:"),  f"{header.hours_100:.2f}"],
            [_h("שעות 125%:"),  f"{header.hours_125:.2f}"],
            [_h("שעות 150%:"),  f"{header.hours_150:.2f}"],
        ]
        if header.bonus:
            smry.append([_h("בונוס:"),    f"\u20aa{header.bonus:.2f}"])
        if header.travel:
            smry.append([_h("נסיעות:"),  f"\u20aa{header.travel:.2f}"])
        st = Table(smry, colWidths=[3.2*cm, 2.2*cm])
        st.setStyle(TableStyle([
            ("FONTNAME",      (0,0),(-1,-1), font),
            ("FONTSIZE",      (0,0),(-1,-1), 8),
            ("ALIGN",         (0,0),(-1,-1), "CENTER"),
            ("BOX",           (0,0),(-1,-1), 0.5, _BORDER),
            ("INNERGRID",     (0,0),(-1,-1), 0.5, _BORDER),
            ("BACKGROUND",    (0,0),(0,-1),   _LIGHT),
        ]))
        elements.append(st)
        elements += _disclaimer_elements(font)
        doc.build(elements)
        return buf.getvalue()
