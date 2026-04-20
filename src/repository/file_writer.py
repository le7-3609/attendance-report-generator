"""File writer repository — writes HTML and PDF outputs."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


class FileWriter:
    """Writes rendered HTML and PDF files to an output directory."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _timestamped_stem(self, source_filename: str, report_type: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"attendance_report_{report_type}_{ts}"

    def write_html(self, stem: str, content: str) -> Path:
        path = self.output_dir / f"{stem}.html"
        path.write_text(content, encoding="utf-8")
        return path

    def write_pdf(self, stem: str, content: bytes) -> Path:
        path = self.output_dir / f"{stem}.pdf"
        path.write_bytes(content)
        return path

    def make_stem(self, source_filename: str, report_type: str) -> str:
        return self._timestamped_stem(source_filename, report_type)
