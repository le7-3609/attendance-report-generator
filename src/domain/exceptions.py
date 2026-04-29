"""Domain-specific exceptions for the attendance report pipeline."""
from __future__ import annotations


class ParseError(ValueError):
    """Raised when a parser cannot extract meaningful data from input text."""


class TransformationError(RuntimeError):
    """Raised when a variator cannot produce a valid variation."""
