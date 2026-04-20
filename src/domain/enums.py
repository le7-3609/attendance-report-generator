from enum import Enum, auto


class ReportType(Enum):
    TYPE_A = "type_a"  # דוח נוכחות חודשי — portrait, hourly rate, summary at top
    TYPE_B = "type_b"  # נ.ע. הנשר — landscape, overtime tiers, summary at bottom
    UNKNOWN = "unknown"
