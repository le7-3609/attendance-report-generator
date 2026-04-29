"""Entry-point: delegates all logic to cli.py.

Usage:
    python -m src.main <pdf_or_folder> [<pdf_or_folder> ...]
    python -m src.cli  <pdf_or_folder> [<pdf_or_folder> ...]   # equivalent
"""
from __future__ import annotations

import sys

from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
