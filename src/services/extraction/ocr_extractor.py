"""OCR extractor — converts PDF pages to images then runs Tesseract.

Uses pypdfium2 to render pages (no Poppler dependency needed on Windows).
Image preprocessing (greyscale, contrast boost, sharpening) improves accuracy
on Hebrew scans.
"""
from __future__ import annotations

import logging

import pypdfium2 as pdfium
import pytesseract
from PIL import Image

from src.services.extraction.base import BaseExtractor
from src.services.extraction.tesseract_setup import (
    OCR_LANG,
    TESSERACT_CONFIG,
    configure_tesseract,
    preprocess_image,
)

logger = logging.getLogger(__name__)


class OcrExtractor(BaseExtractor):
    """Extracts text from scanned (image-based) PDF pages via OCR.

    Renders each page with pypdfium2 at the requested DPI then sends the
    resulting PIL Image to Tesseract.  No Poppler installation required.
    """

    def __init__(self, dpi: int = 300, lang: str = OCR_LANG):
        self.dpi = dpi
        self.lang = lang
        self._scale = dpi / 72  # pypdfium2 uses 72 DPI as baseline
        configure_tesseract()

    def _render_page(self, page: pdfium.PdfPage) -> Image.Image:
        bitmap = page.render(scale=self._scale, rotation=0)
        return preprocess_image(bitmap.to_pil())

    def extract(self, pdf_bytes: bytes) -> str:
        pages_text: list[str] = []
        pdf = pdfium.PdfDocument(pdf_bytes)
        try:
            for page_idx in range(len(pdf)):
                page = pdf[page_idx]
                img = self._render_page(page)
                try:
                    text = pytesseract.image_to_string(
                        img, lang=self.lang, config=TESSERACT_CONFIG
                    )
                    if text.strip():
                        pages_text.append(text.strip())
                except pytesseract.TesseractNotFoundError as exc:
                    raise RuntimeError(
                        "Tesseract is not installed or not in PATH. "
                        "Please install it from https://github.com/UB-Mannheim/tesseract/wiki"
                    ) from exc
                finally:
                    page.close()
        finally:
            pdf.close()
        return "\n".join(pages_text)
