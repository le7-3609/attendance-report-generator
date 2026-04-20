"""PDF reader repository — reads raw bytes from a path."""
from __future__ import annotations

from pathlib import Path


class PdfReader:
    """Simple file-system reader for PDF files."""

    def read(self, path: str | Path) -> bytes:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a .pdf file, got: {path.suffix}")
        return path.read_bytes()

    def list_pdfs(self, folder: str | Path) -> list[Path]:
        """Return all PDF paths inside *folder* (non-recursive)."""
        folder = Path(folder)
        return sorted(folder.glob("*.pdf"))
