"""Text extractor using pdfplumber (native embedded text)."""
from __future__ import annotations

import io

import pdfplumber

from src.services.extraction.base import BaseExtractor


class TextExtractor(BaseExtractor):
    """Extracts text from a PDF that has embedded selectable text."""

    def extract(self, pdf_bytes: bytes) -> str:
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Try structured table extraction first for tabular reports
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row:
                                cells = [cell or "" for cell in row]
                                pages.append(" | ".join(cells))
                else:
                    text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if text:
                        pages.append(text)
        return "\n".join(pages)
