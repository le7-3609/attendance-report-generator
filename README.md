# Attendance Report Variation Generator

Generate realistic, structurally-identical variations of Hebrew attendance PDF reports.
Upload a scanned PDF or image — get a new PDF with slightly different times and recalculated totals.

---

## How it works

```
PDF / Image ►► Extract text ►► Classify type ►► Parse ►► Vary ►► Render HTML ►► PDF
              (pdfplumber       (A or B)        (structure   (random    (Jinja2      (ReportLab)
               ► OCR fallback)                  → models)    rules)
```

### Report types

| | Type A | Type B |
|---|---|---|
| Title | דוח נוכחות חודשי | נ.ע. הנשר בע"מ — דוח נוכחות מפורט |
| Orientation | A4 Portrait | A4 Landscape |
| Columns | Date, Weekday, Entry, Exit, Total, Notes | Date, Weekday, Location, Entry, Exit, Break, Total, 100%, 125%, 150% |
| Summary | Work days, hours, hourly rate, total pay | Days, hours split by overtime tier |

### Variation rules

**Type A**
- Entry adjusted ±0–15 min (clamped 07:00–10:00)
- Shift duration varies ±0–10 min; enforced 2.0 h–5.0 h
- Weekday name re-derived from calendar date
- Summary totals recalculated from rows

**Type B**
- Entry adjusted ±0–10 min
- Exit adjusted to maintain similar gross duration ±10 min
- Break time varied ±5 min; defaults to 30 min when OCR found none
- Overtime split: 0–8 h → 100%, 8–10 h → 125%, >10 h → 150%
- Location filled from OCR; falls back to a plausible city when missing
- Summary totals recalculated from rows

---

## Prerequisites

1. **Python 3.11+**
2. **Tesseract OCR** — required for scanned (image-based) PDFs and image uploads
   - Windows installer: <https://github.com/UB-Mannheim/tesseract/wiki>
   - Default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe` (auto-detected)
   - Hebrew language data (`heb.traineddata`) is bundled in the `tessdata/` folder — no extra download needed

---

## Install

### With UV (recommended)

```powershell
# From the attendance-generator/ directory
uv venv
.venv\Scripts\activate
uv pip install -e .
```

### With pip

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the Gradio web interface

The web interface is the easiest way to use the tool.
It accepts **PDF files** (both text-based and scanned) as well as images (PNG, JPG, TIFF, BMP, WEBP).

```powershell
# Make sure your venv is activated, then:
python gradio_app.py
```

A browser tab opens automatically at `http://127.0.0.1:7860`.

**How to use:**
1. Click **העלה קובץ PDF או תמונה** and select your file.
2. Click **⚙️ עבד דוח**.
3. The status box shows the detected report type and row count.
4. Click the generated file in the **PDF מוכן להורדה** box to download it.

> **Tip:** For scanned PDFs or low-quality images, make sure the scan is at least 200 DPI
> and that the text is not rotated. The tool applies contrast boosting and sharpening
> automatically, but very blurry or skewed documents will reduce OCR accuracy.

---

## Running the CLI

The command-line tool processes one or more PDFs in a folder.

```powershell
# Process all PDFs in a folder
python -m src.main ..\input_pdfs\

# Process a single PDF
python -m src.main ..\input_pdfs\report.pdf

# Custom output directory
python -m src.main ..\input_pdfs\ --output-dir ..\output_pdfs\

# Verbose logging
python -m src.main ..\input_pdfs\ --verbose
```

Each run writes two files per input PDF to the output directory:
- `attendance_report_<type>_<timestamp>.html` (preview)
- `attendance_report_<type>_<timestamp>.pdf`

---

## Adapting the tool to your own report format

The classifier, parsers, and renderers are designed to be extended.
Here is what to check or change when your PDFs look different from the defaults.

### 1. The classifier rejects your report (returns UNKNOWN)

Open `src/services/classification/classifier.py`.
Add keyword patterns from your report's header to `_TYPE_A_SIGNALS` or `_TYPE_B_SIGNALS`:

```python
_TYPE_B_SIGNALS = [
    r"שעות\s+נוספות",
    r"125%",
    r"150%",
    r"הפסקה",
    r"נ\.ע\.",
    # ← add your own unique header text here
    r"My Company Name",
]
```

Patterns are Python regex strings matched case-insensitively against the full extracted text.

### 2. The parser misses rows or fields

Open the relevant parser (`src/services/parsing/type_a_parser.py` or `type_b_parser.py`).

- **Dates not found** — check `_DATE_RE`. The default expects `DD/MM/YYYY` or `DD/MM/YY`.
  Change the regex if your format uses `-` separators or `YYYY/MM/DD` order.
- **Times not found** — check `_TIME_RE`. The default expects `H:MM` or `HH:MM`.
- **Summary fields not parsed** — each `_DAYS_RE`, `_TOTAL_HRS_RE`, etc. is a standalone regex.
  Print the raw OCR output (`--verbose` flag) and adjust the patterns
  to match the exact Hebrew/numeric text in your PDFs.

To see the raw extracted text, run:

```powershell
python -m src.main your_report.pdf --verbose 2>&1 | findstr "Extracted"
```

### 3. Variation rules do not match your business rules

Open `src/services/variation/type_a_variator.py` or `type_b_variator.py`.

Key constants you can tune:

| Constant | File | Effect |
|---|---|---|
| `_ENTRY_DELTA_MINUTES` | both | Maximum random shift on entry time |
| `_EXIT_DELTA_MINUTES` | type_b | Maximum random shift on exit time |
| `_REGULAR_THRESHOLD` | type_b | Hours before overtime kicks in (default 8) |
| `_OT_125_HOURS` | type_b | Hours in the 125% band (default 2) |
| `_MIN_SHIFT_H` / `_MAX_SHIFT_H` | both | Clamp on total shift duration |

### 4. The output HTML/PDF looks wrong

Templates are in `templates/`. Edit `type_a.html.j2` or `type_b.html.j2` with standard
Jinja2 syntax. The `header` and `rows` variables match the fields in `src/domain/models.py`.

---

## Extending to a new report type (Type C, D, ...)

1. Add a new value to `src/domain/enums.py` → `ReportType`
2. Add keyword signals in `src/services/classification/classifier.py`
3. Create `src/services/parsing/type_c_parser.py` (extend `BaseParser`)
4. Create `src/services/variation/type_c_variator.py` (extend `BaseVariator`)
5. Create `src/services/rendering/type_c_renderer.py` + `templates/type_c.html.j2`
6. Register all three in their respective `registry.py` files

No other changes are needed.

---

## Run tests

```powershell
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
