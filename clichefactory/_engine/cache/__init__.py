"""Cache implementations: Cacher (NormalizedDoc), local filesystem cache."""
from __future__ import annotations

from clichefactory._engine.cache.base_cacher import Cacher
from clichefactory._engine.cache.file_system_cacher import FileSystemCacher

__all__ = [
    "Cacher",
    "FileSystemCacher",
]
