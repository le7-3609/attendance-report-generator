"""
Attendance Report Variation Generator
======================================
CLI entry-point.  Usage:
    python -m src.main <pdf_or_folder> [<pdf_or_folder> ...]

Each positional argument can be:
  - A path to a single .pdf file
  - A directory — all *.pdf files inside will be processed

Outputs are written to the sibling  output_pdfs/  folder.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.domain.enums import ReportType
from src.repository.file_writer import FileWriter
from src.repository.pdf_reader import PdfReader
from src.services.classification.classifier import Classifier
from src.services.extraction.pipeline import ExtractionPipeline
from src.services.parsing.registry import get_parser
from src.services.pdf_service import PdfService
from src.services.rendering.registry import get_renderer
from src.services.variation.registry import get_variator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def _resolve_pdf_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    reader = PdfReader()
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            found = reader.list_pdfs(p)
            if not found:
                logger.warning("No PDF files found in directory: %s", p)
            paths.extend(found)
        elif p.is_file():
            paths.append(p)
        else:
            logger.error("Path not found: %s", p)
    return paths


def _default_output_dir(first_pdf: Path) -> Path:
    """Place output alongside an `output_pdfs` sibling of the PDF's parent."""
    candidate = first_pdf.parent.parent / "output_pdfs"
    if candidate.exists():
        return candidate
    return first_pdf.parent / "output_pdfs"


def process_pdf(
    pdf_path: Path,
    writer: FileWriter,
    extractor: ExtractionPipeline,
    classifier: Classifier,
    pdf_service: PdfService,
) -> bool:
    """Process a single PDF.  Returns True on success."""
    logger.info("━" * 60)
    logger.info("Processing: %s", pdf_path.name)

    # ── Input validation ──────────────────────────────────────────────────────
    _MAX_BYTES = 50 * 1024 * 1024  # 50 MB — guard against huge scans
    _PDF_MAGIC = b"%PDF-"

    file_size = pdf_path.stat().st_size
    if file_size == 0:
        logger.error("File %s is empty — skipping.", pdf_path.name)
        return False
    if file_size > _MAX_BYTES:
        logger.error(
            "File %s is too large (%d MB > 50 MB limit) — skipping.",
            pdf_path.name, file_size // (1024 * 1024),
        )
        return False
    with pdf_path.open("rb") as fh:
        if fh.read(5) != _PDF_MAGIC:
            logger.error("File %s does not appear to be a valid PDF — skipping.", pdf_path.name)
            return False
    # ──────────────────────────────────────────────────────────────────────────

    try:
        # 1. Read
        pdf_bytes = PdfReader().read(pdf_path)

        # 2. Extract text
        text = extractor.extract(pdf_bytes)
        if not text.strip():
            logger.error("No text could be extracted from %s — skipping.", pdf_path.name)
            return False
        logger.debug("Extracted %d characters.", len(text))

        # 3. Classify
        report_type = classifier.classify(text)
        if report_type == ReportType.UNKNOWN:
            logger.error(
                "Could not determine report type for %s — skipping.", pdf_path.name
            )
            return False
        logger.info("Detected report type: %s", report_type.value)

        # 4. Parse
        parser = get_parser(report_type)
        report_data = parser.parse(text, source_filename=pdf_path.name)
        logger.info("Parsed %d attendance rows.", len(report_data.rows))

        # 5. Vary
        variator = get_variator(report_type)
        varied_data = variator.vary(report_data)
        logger.info("Variation complete — %d rows in output.", len(varied_data.rows))

        # 6. Render HTML
        renderer = get_renderer(report_type)
        html = renderer.render(varied_data)

        # 7. Write HTML
        stem = writer.make_stem(pdf_path.stem, report_type.value)
        html_path = writer.write_html(stem, html)
        logger.info("HTML written → %s", html_path.name)

        # 8. Generate & write PDF
        pdf_out = pdf_service.generate(varied_data)
        pdf_path_out = writer.write_pdf(stem, pdf_out)
        logger.info("PDF  written → %s", pdf_path_out.name)

        return True

    except Exception as exc:
        logger.exception("Failed to process %s: %s", pdf_path.name, exc)
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate realistic variations of attendance PDF reports."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="PDF file(s) or folder(s) containing PDFs to process.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="Directory where output files will be written. "
             "Defaults to an output_pdfs/ folder next to the first input.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    pdf_paths = _resolve_pdf_paths(args.inputs)
    if not pdf_paths:
        logger.error("No PDF files to process.")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else _default_output_dir(pdf_paths[0])
    logger.info("Output directory: %s", output_dir)

    writer = FileWriter(output_dir)
    extractor = ExtractionPipeline()
    classifier = Classifier()
    pdf_service = PdfService()

    successes = 0
    for pdf_path in pdf_paths:
        if process_pdf(pdf_path, writer, extractor, classifier, pdf_service):
            successes += 1

    logger.info("━" * 60)
    logger.info("Done — %d/%d files processed successfully.", successes, len(pdf_paths))
    return 0 if successes == len(pdf_paths) else 1


if __name__ == "__main__":
    sys.exit(main())
