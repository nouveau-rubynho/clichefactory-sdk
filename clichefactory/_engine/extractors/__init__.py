"""Backward-compatible re-export of extractors.

These classes live in ``clichefactory_internal.extractors`` and are re-exported
here so internal services can import from ``clichefactory._engine``.
"""

try:
    from clichefactory_internal.extractors import BaseExtractor, VerifiedExtractor
except ImportError:
    pass

__all__ = ["BaseExtractor", "VerifiedExtractor"]
