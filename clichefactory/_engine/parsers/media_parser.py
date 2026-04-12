# aio/parsers/media_parser.py
from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
from typing import TYPE_CHECKING, Any, Callable, final

if TYPE_CHECKING:
    from clichefactory._engine.parsers.media_parser_registry import MediaParserRegistry

from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.cache.base_cacher import Cacher


class MediaParser(ABC):
    """
    Base class for media parsers.

    - Subclasses implement `document_parse`.
    - Caching is handled here, via a pluggable `Cacher`. You can implement cacher for file_caching, Redis, ...
    """

    def __init__(
        self,
        cacher: Cacher | None = None,
        cache_key_fn: Callable[[bytes, str], str] | None = None,
        media_parser_registry: "MediaParserRegistry | None" = None,
        **kwargs: Any,
    ) -> None:
        """
        :param cacher: Cacher implementation (FileSystemCacher, RedisCacher, ...)
        :param cache_key_fn: optional function (content, filename) -> key string.
                             If not provided, a default hash-based strategy is used.
        :param media_parser_registry: optional registry passed when created via registry.create_parser();
                                     parsers that need to resolve other parsers (e.g. PDF) use this.
        """
        self._cacher = cacher
        self._cache_key_fn = cache_key_fn or MediaParser.default_cache_key
        self._media_parser_registry = media_parser_registry

    @abstractmethod
    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        """Subclasses must implement the document parsing step"""
        ...

    # ---------- Caching helpers (no need to override in subclasses) ----------
    @staticmethod
    def default_cache_key( content: bytes, filename: str) -> str:
        """
        Default cache key strategy: hash of (filename + content).

        - Using the content ensures that if a file changes but keeps
          the same name, you don't get stale cache entries.
        """
        h = hashlib.sha256()
        h.update(filename.encode("utf-8", errors="ignore"))
        h.update(content)  # Perhaps not needed?
        return h.hexdigest()

    # ---------- Public API ----------
    @final
    def parse(self, content: bytes, filename: str, use_cache: bool = True) -> NormalizedDoc:
        """
        Public method that:
        - Computes a cache key (default: hash(filename + content))
        - If a cacher is configured and use_cache=True:
            - attempts to load from cache
            - otherwise parses and saves to cache
        - If no cacher is configured or use_cache=False:
            - simply calls document_parse

        Subclasses don't override this; they just implement `document_parse`.
        """
        cacher = self._cacher
        key = self._cache_key_fn(content=content, filename=filename) # type: ignore

        # 1. Try cache first
        if use_cache and cacher is not None and cacher.exists(key):
            return cacher.load(key)

        # 2. Parse the document
        doc = self.document_parse(content=content, filename=filename)

        # 3. Store in cache
        if use_cache and cacher is not None:
            cacher.save(key, doc)

        return doc
