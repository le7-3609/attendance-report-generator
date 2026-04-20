"""Shared Tesseract configuration and image preprocessing utilities.

Centralised here so that both OcrExtractor and gradio_app.py use the exact
same settings.  Previously both files duplicated these constants and functions,
meaning a change in one would silently diverge from the other.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Tesseract runtime config: OEM 3 = LSTM + legacy, PSM 6 = uniform text block.
TESSERACT_CONFIG: str = r"--oem 3 --psm 6"

# Default OCR language(s) — Hebrew primary, English fallback.
OCR_LANG: str = "heb+eng"

# Local tessdata bundled with the project (heb.traineddata + eng.traineddata).
# Resolved from the project root regardless of working directory.
_PROJECT_TESSDATA: Path = Path(__file__).resolve().parent.parent.parent.parent / "tessdata"

# Common Windows installation paths for Tesseract.
_TESSERACT_PATHS: list[Path] = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\tesseract\tesseract.exe"),
    Path(r"C:\ProgramData\chocolatey\bin\tesseract.exe"),
]


def configure_tesseract() -> None:
    """Point pytesseract at Tesseract and configure local tessdata prefix.

    Safe to call multiple times — subsequent calls are no-ops if Tesseract
    is already visible in PATH.
    """
    if _PROJECT_TESSDATA.exists():
        os.environ["TESSDATA_PREFIX"] = str(_PROJECT_TESSDATA)

    if shutil.which("tesseract"):
        return  # already accessible via PATH

    for path in _TESSERACT_PATHS:
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            logger.info("Tesseract found at %s", path)
            return

    logger.warning(
        "Tesseract not found. Install from "
        "https://github.com/UB-Mannheim/tesseract/wiki"
    )


def preprocess_image(img: Image.Image) -> Image.Image:
    """Apply standard preprocessing to improve OCR accuracy on Hebrew scans.

    Steps: greyscale → contrast boost → sharpening.
    """
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)
    return img
