"""Thin argparse CLI — delegates all pipeline work to app.process_pdf()."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.app import process_pdf
from src.repository.file_writer import FileWriter
from src.repository.pdf_reader import PdfReader
from src.services.classification.classifier import Classifier
from src.services.extraction.pipeline import ExtractionPipeline
from src.services.pdf_service import PdfService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cli")


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
    candidate = first_pdf.parent.parent / "output_pdfs"
    if candidate.exists():
        return candidate
    return first_pdf.parent / "output_pdfs"


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
