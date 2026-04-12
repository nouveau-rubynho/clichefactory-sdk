from __future__ import annotations

import logging
from typing import Callable, Optional, Type

from clichefactory._engine.cache.base_cacher import Cacher
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser


logger = logging.getLogger(__name__)


class FallbackMediaParser(MediaParser):
    """
    MediaParser that delegates to a primary parser and falls back to a secondary
    parser when the primary fails (or produces low-quality output if quality_checker is provided).

    - Caching is handled at this wrapper level via MediaParser.parse().
    - Primary and fallback parsers are instantiated inside document_parse and
      their own caching is bypassed (document_parse is called directly).
    """

    def __init__(
        self,
        *,
        primary_cls: Type[MediaParser],
        fallback_cls: Type[MediaParser],
        quality_checker: Optional[Callable[[NormalizedDoc, bytes, str], bool]] = None,
        cacher: Cacher | None = None,
        cache_key_fn: Callable[[bytes, str], str] | None = None,
        media_parser_registry=None,
        **kwargs,
    ) -> None:
        super().__init__(
            cacher=cacher,
            cache_key_fn=cache_key_fn,
            media_parser_registry=media_parser_registry,
            **kwargs,
        )
        self._primary_cls = primary_cls
        self._fallback_cls = fallback_cls
        self._quality_checker = quality_checker

    def _make_parser(self, parser_cls: Type[MediaParser]) -> MediaParser:
        """
        Instantiate an inner parser with the same cacher/cache_key_fn/registry
        wiring as this wrapper.
        """
        return parser_cls(
            cacher=self._cacher,
            cache_key_fn=self._cache_key_fn,
            media_parser_registry=self._media_parser_registry,
        )

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        primary = self._make_parser(self._primary_cls)

        # 1) Try primary parser
        try:
            doc = primary.document_parse(content, filename)
        except Exception as e:
            logger.warning(
                "Primary parser %s failed for %s: %s; falling back to %s",
                self._primary_cls.__name__,
                filename,
                e,
                self._fallback_cls.__name__,
            )
            fallback = self._make_parser(self._fallback_cls)
            return fallback.document_parse(content, filename)

        # 2) Run quality check if configured; if good enough, return primary result
        if self._quality_checker is None:
            return doc

        try:
            is_bad = self._quality_checker(doc, content, filename)
        except Exception as e:
            logger.warning(
                "Quality checker raised %s for %s; keeping primary result from %s",
                e,
                filename,
                self._primary_cls.__name__,
            )
            is_bad = False

        if not is_bad:
            return doc

        # 3) Fallback path when primary output is considered low-quality
        logger.info(
            "Primary parser %s produced low-quality output for %s; falling back to %s",
            self._primary_cls.__name__,
            filename,
            self._fallback_cls.__name__,
        )
        fallback = self._make_parser(self._fallback_cls)
        return fallback.document_parse(content, filename)

