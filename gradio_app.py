"""
Gradio Web Interface — Attendance Report Generator
====================================================
Upload a PDF scan or an image of an attendance report → get a generated PDF variation.

Run:
    python gradio_app.py
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import gradio as gr
import pdfplumber
import pypdfium2
import pytesseract
from PIL import Image

from src.domain.enums import ReportType
from src.services.classification.classifier import Classifier
from src.services.extraction.tesseract_setup import (
    OCR_LANG,
    TESSERACT_CONFIG,
    configure_tesseract,
    preprocess_image,
)
from src.services.parsing.registry import get_parser
from src.services.pdf_service import PdfService
from src.services.rendering.registry import get_renderer
from src.services.variation.registry import get_variator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gradio_app")

configure_tesseract()

# ── Singleton services (created once at startup) ────────────────────────────────

_classifier = Classifier()
_pdf_service = PdfService()


# ── Core processing function ────────────────────────────────────────────────────

# Maximum accepted upload size (bytes).  Rejects files that would exhaust
# memory or hang Tesseract.
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
# Magic bytes that every valid PDF file starts with.
_PDF_MAGIC = b"%PDF-"


def _validate_upload(file_path: str, ext: str) -> str | None:
    """Return an error message string if the file fails basic validation,
    or None if it is acceptable."""
    path = Path(file_path)
    size = path.stat().st_size
    if size == 0:
        return "⚠️ הקובץ ריק. אנא העלה קובץ תקין."
    if size > _MAX_FILE_BYTES:
        mb = size // (1024 * 1024)
        return f"⚠️ הקובץ גדול מדי ({mb} MB). הגדל המירבי הוא 50 MB."
    if ext == ".pdf":
        with open(file_path, "rb") as fh:
            header = fh.read(5)
        if header != _PDF_MAGIC:
            return "⚠️ הקובץ אינו PDF תקין (חתימת הקובץ שגויה)."
    return None


def _ocr_image(img: Image.Image) -> str:
    """Run Tesseract OCR on a PIL image and return the extracted text."""
    return pytesseract.image_to_string(
        preprocess_image(img), lang=OCR_LANG, config=TESSERACT_CONFIG
    )


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file.

    1. Try pdfplumber (fast, works on text-based PDFs).
    2. If the page is image-only (scanned), render via pypdfium2 and OCR each page.
    """
    pages_text: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)

    combined = "\n".join(pages_text)
    if combined.strip():      # text-based PDF — done
        logger.info("pdfplumber extracted %d characters from PDF.", len(combined))
        return combined

    # Scanned / image-only PDF — render pages and OCR
    logger.info("PDF has no selectable text; falling back to OCR per page.")
    doc = pypdfium2.PdfDocument(pdf_path)
    ocr_parts: list[str] = []
    for page in doc:
        bitmap = page.render(scale=2.0)   # 2× for better OCR accuracy
        pil_img = bitmap.to_pil()
        ocr_parts.append(_ocr_image(pil_img))
    doc.close()
    combined = "\n".join(ocr_parts)
    logger.info("OCR fallback extracted %d characters.", len(combined))
    return combined


def process_file(upload) -> tuple[str | None, str]:
    """
    Main Gradio handler — accepts a PDF or image file.

    Parameters
    ----------
    upload : file-like object returned by gr.File, or None.

    Returns
    -------
    (pdf_path, status_message)
        pdf_path  – path to the generated PDF file (or None on failure)
        status_message – Hebrew/English feedback for the user
    """
    if upload is None:
        return None, "⚠️ לא הועלה קובץ. אנא העלה קובץ PDF או תמונה של דוח נוכחות."

    # Gradio 4.x passes an object with a .name attribute (temp path on disk)
    file_path: str = upload.name if hasattr(upload, "name") else str(upload)
    ext = Path(file_path).suffix.lower()

    # Validate before doing any expensive work
    validation_error = _validate_upload(file_path, ext)
    if validation_error:
        return None, validation_error

    # 1. Extract text
    try:
        if ext == ".pdf":
            text = _extract_text_from_pdf(file_path)
        else:
            img = Image.open(file_path)
            text = _ocr_image(img)
            logger.info("OCR extracted %d characters from image.", len(text))
    except pytesseract.TesseractNotFoundError:
        return None, (
            "❌ Tesseract אינו מותקן. "
            "התקן אותו מ‑ https://github.com/UB-Mannheim/tesseract/wiki"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Extraction failed: %s", exc)
        return None, f"❌ שגיאה בחילוץ הטקסט: {exc}"

    if not text.strip():
        return None, "⚠️ לא הצלחנו לחלץ טקסט מהקובץ. ודא שהקובץ ברור ומכיל טקסט."

    # 2. Classify
    report_type = _classifier.classify(text)
    if report_type == ReportType.UNKNOWN:
        return None, (
            "❌ לא ניתן לזהות את סוג הדוח.\n"
            "הממשק תומך רק בדוחות נוכחות מסוג A (כרטיס עובד חודשי) "
            "או סוג B (דיווח שעות נוספות).\n"
            "ודא שהתמונה מכילה דוח נוכחות מוכר."
        )
    logger.info("Detected report type: %s", report_type.value)

    # 3. Parse
    try:
        parser = get_parser(report_type)
        report_data = parser.parse(text, source_filename="uploaded_image")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Parsing failed: %s", exc)
        return None, f"❌ שגיאה בניתוח הנתונים: {exc}"

    # 4. Vary
    try:
        variator = get_variator(report_type)
        varied_data = variator.vary(report_data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Variation failed: %s", exc)
        return None, f"❌ שגיאה ביצירת הווריאציה: {exc}"

    # 5. Generate PDF bytes
    try:
        pdf_bytes = _pdf_service.generate(varied_data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("PDF generation failed: %s", exc)
        return None, f"❌ שגיאה ביצירת ה‑PDF: {exc}"

    # 6. Save to a named temp file so Gradio can serve it for download
    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf",
            prefix=f"attendance_{report_type.value}_",
            delete=False,
        )
        tmp.write(pdf_bytes)
        tmp.close()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to write temp PDF: %s", exc)
        return None, f"❌ שגיאה בשמירת הקובץ: {exc}"

    success_msg = (
        f"✅ הדוח עובד בהצלחה!\n"
        f"סוג: {'A — כרטיס עובד חודשי' if report_type == ReportType.TYPE_A else 'B — דוח שעות נוספות'}\n"
        f"שורות נוכחות: {len(varied_data.rows)}"
    )
    return tmp.name, success_msg


# ── Gradio UI ───────────────────────────────────────────────────────────────────

with gr.Blocks(title="מחולל דוחות נוכחות", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 📋 מחולל דוחות נוכחות
        ### העלה קובץ PDF סרוק או תמונה של דוח נוכחות — קבל קובץ PDF מוכן להורדה

        **סוגי דוחות נתמכים:**
        - **סוג A** — דוח נוכחות חודשי (כרטיס עובד, מחיר לשעה)
        - **סוג B** — דוח שעות נוספות (125% / 150%)

        **סוגי קבצים נתמכים:** PDF, PNG, JPG, TIFF, BMP, WEBP
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="העלה קובץ PDF או תמונה של הדוח",
                file_types=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"],
            )
            submit_btn = gr.Button("⚙️ עבד דוח", variant="primary", size="lg")

        with gr.Column(scale=1):
            status_output = gr.Textbox(
                label="סטטוס",
                interactive=False,
                lines=5,
            )
            file_output = gr.File(
                label="PDF מוכן להורדה",
                visible=True,
            )

    submit_btn.click(
        fn=process_file,
        inputs=[file_input],
        outputs=[file_output, status_output],
    )

    gr.Markdown(
        """
        ---
        *הערה:
         עבור קבצי 
         PDF
         סרוקים (תמונה בלבד), הכלי מבצע 
         OCR 
         (זיהוי תווים) אוטומטי.
         לקבלת תוצאות מיטביות, השתמש בקובץ ברור ובאיכות גבוהה.*
        """
    )


if __name__ == "__main__":
    demo.launch(inbrowser=True)
