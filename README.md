# Attendance Report Variation Generator

Generate realistic, structurally-identical variations of Hebrew attendance PDF reports.
Upload a scanned PDF or image — get a new PDF with slightly different times and recalculated totals.

---

## How it works

```
PDF / Image ►► Extract text ►► Classify type ►► Parse ►► Transform ►► Render HTML ►► PDF
              (pdfplumber       (A or B)        (structure   (strategy + (Jinja2      (ReportLab)
               ► OCR fallback)                  → models)    validation)
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

### Validation and safe fallback

After the strategy produces a converted row/report, a validation decorator audits invariants
(entry/exit consistency, total-hours sanity, overtime tiers summing correctly, etc.).

If validation fails for a row, the transformation layer **keeps the original row** and continues,
so a single bad OCR line does not break the whole output.

### OCR hour normalization (base-60 minutes)

Some reports (and OCR output) encode durations like `7.30` meaning **7 hours 30 minutes**
(not 7.30 decimal hours). The parsers normalize hour tokens using a base‑60 minutes rule:

- `7.30` → `7.50`
- `7.70` (7h70m) → `8.17`

---

## Prerequisites

1. **Python 3.11+**
2. **Tesseract OCR** — required for scanned (image-based) PDFs
   - Windows installer: <https://github.com/UB-Mannheim/tesseract/wiki>
   - Default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe` (auto-detected)
   - Hebrew language data (`heb.traineddata`) is bundled in the `tessdata/` folder — no extra download needed

---

## Install

### With UV (recommended)

```powershell
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

## Running the CLI

```powershell
# Process a single PDF — output goes to a separate folder
attendance-report input_pdfs\report.pdf -o output_pdfs\

# Process all PDFs in a folder
attendance-report input_pdfs\ -o output_pdfs\

# Verbose logging
attendance-report input_pdfs\ -o output_pdfs\ --verbose
```

Or via `python -m`:

```powershell
python -m src.main input_pdfs\ -o output_pdfs\
```

Each run writes two files per input PDF to the output directory:
- `attendance_report_<type>_<timestamp>.html` (preview)
- `attendance_report_<type>_<timestamp>.pdf`

---

## Running with Docker

### Build

```powershell
docker build -t attendance-report .
```

### Run (Linux / macOS)

```bash
# Single file
docker run --rm \
  -v $(pwd)/samples:/data/input \
  -v $(pwd)/output:/data/output \
  attendance-report /data/input/report.pdf -o /data/output/

# Entire folder
docker run --rm \
  -v $(pwd)/samples:/data/input \
  -v $(pwd)/output:/data/output \
  attendance-report /data/input/ -o /data/output/
```

### Run (Windows PowerShell)

Docker Desktop on Windows requires absolute paths with forward slashes:

```powershell
docker run --rm `
  -v "C:/path/to/samples:/data/input" `
  -v "C:/path/to/output:/data/output" `
  attendance-report /data/input/report.pdf -o /data/output/
```

> **Note:** Docker Desktop may not have access to drives other than C by default.
> If your files are on another drive, copy them to C first, or add the drive under
> Docker Desktop → Settings → Resources → File Sharing.

---

## Adapting the tool to your own report format

### 1. The classifier rejects your report (returns UNKNOWN)

Open `src/services/classification/classifier.py`.
Add keyword patterns from your report's header to `_TYPE_A_SIGNALS` or `_TYPE_B_SIGNALS`:

```python
_TYPE_B_SIGNALS = [
    r"שעות\s+נוספות",
    r"125%",
    r"My Company Name",   # ← add your own unique header text here
]
```

### 2. The parser misses rows or fields

Open the relevant parser (`src/services/parsing/type_a_parser.py` or `type_b_parser.py`).

- **Dates not found** — check `_DATE_RE`. Default expects `DD/MM/YYYY` or `DD/MM/YY`.
- **Times not found** — check `_TIME_RE`. Default expects `H:MM` or `HH:MM`.
- **Summary fields not parsed** — adjust `_DAYS_RE`, `_TOTAL_HRS_RE`, etc.

To see the raw extracted text:

```powershell
attendance-report your_report.pdf --verbose 2>&1 | findstr "Extracted"
```

### 3. Variation rules do not match your business rules

Edit `src/config/rules.py`:

- `TypeAVariationRules`: entry window, shift duration clamp, deltas, fallback hourly rate range
- `TypeBVariationRules`: deltas, break bounds, overtime thresholds, long-shift probability/range

### 4. The output HTML/PDF looks wrong

Templates are in `templates/`. Edit `type_a.html.j2` or `type_b.html.j2` with standard
Jinja2 syntax.

---

## Extending to a new report type (Type C, D, ...)

1. Add a new value to `src/domain/enums.py` → `ReportType`
2. Add keyword signals in `src/services/classification/classifier.py`
3. Create `src/services/parsing/type_c_parser.py` (extend `BaseParser`)
4. Create `src/services/variation/type_c_variator.py` (implement `BaseVariator`)
5. Create `src/services/rendering/type_c_renderer.py` + `templates/type_c.html.j2`
6. Register all three in their respective `registry.py` files

---

## Run tests

```powershell
pip install -e ".[dev]"
pytest tests/ -v
```
