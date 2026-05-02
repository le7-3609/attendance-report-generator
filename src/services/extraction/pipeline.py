"""Extraction pipeline: tries native text first, falls back to OCR."""
from __future__ import annotations

import logging
import os

from src.services.extraction.ocr_extractor import OcrExtractor
from src.services.extraction.text_extractor import TextExtractor

logger = logging.getLogger(__name__)

class ExtractionPipeline:
    """Extracts text from any PDF — text-based or scanned."""

    def __init__(
        self,
        ocr_dpi: int = 300,
        ocr_lang: str = "heb+eng",
        min_text_length: int | None = None,
    ):
        if min_text_length is None:
            min_text_length = int(os.environ.get("ATTENDANCE_MIN_TEXT_LENGTH", "50"))
        self._text = TextExtractor()
        self._ocr = OcrExtractor(dpi=ocr_dpi, lang=ocr_lang)
        self._min_text_length = min_text_length

    def extract(self, pdf_bytes: bytes) -> str:
        logger.debug("Attempting native text extraction …")
        try:
            text = self._text.extract(pdf_bytes)
        except Exception as exc:
            logger.warning("Native text extraction failed (%s), falling back to OCR.", exc)
            text = ""

        if len(text.strip()) >= self._min_text_length:
            logger.debug("Native text extraction succeeded (%d chars).", len(text))
            return text

        logger.info(
            "Native text too short (%d chars, threshold=%d). Falling back to OCR …",
            len(text.strip()), self._min_text_length,
        )
        try:
            return self._ocr.extract(pdf_bytes)
        except Exception as exc:
            raise RuntimeError(
                f"Both text extraction and OCR failed. Last OCR error: {exc}"
            ) from exc
