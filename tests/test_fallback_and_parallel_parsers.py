from __future__ import annotations

from pathlib import Path
from typing import Any

from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.fallback_media_parser import FallbackMediaParser
from clichefactory._engine.parsers.media_parser import MediaParser


class _DummyDoc(NormalizedDoc):
    def __init__(self, markdown: str, pages: int = 1) -> None:
        self.filename = None
        self.summary_text = ""
        self.media_type = "application/octet-stream"
        self.pages = [None] * pages  # type: ignore[list-item]
        self.sections = []
        self.images = []
        self.tables = []
        self._markdown = markdown

    def get_plain_text(self) -> str:
        return self._markdown

    def get_markdown(self) -> str:
        return self._markdown


class _PrimaryOkParser(MediaParser):
    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        return _DummyDoc("some reasonable content", pages=1)


class _PrimaryExceptionParser(MediaParser):
    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        raise RuntimeError("boom")


class _FallbackParser(MediaParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._called = False

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        self._called = True
        return _DummyDoc("fallback content", pages=1)


def _run_fallback(
    primary_cls: type[MediaParser],
) -> tuple[NormalizedDoc, _FallbackParser | None]:
    # Small helper to run FallbackMediaParser with a given primary.
    # fallback_instance is set only when fallback is actually used.
    fallback_instance: _FallbackParser | None = None

    class _WrapperFallback(_FallbackParser):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            nonlocal fallback_instance
            super().__init__(*args, **kwargs)
            fallback_instance = self

    wrapper = FallbackMediaParser(
        primary_cls=primary_cls,
        fallback_cls=_WrapperFallback,
    )
    doc = wrapper.parse(b"dummy", "dummy.pdf", use_cache=False)
    return doc, fallback_instance


def test_fallback_media_parser_keeps_good_primary_result() -> None:
    doc, fallback = _run_fallback(_PrimaryOkParser)
    assert isinstance(doc, _DummyDoc)
    assert doc.get_markdown() == "some reasonable content"
    # Fallback should not be called when primary output is fine
    assert fallback is None or not fallback._called


def test_fallback_media_parser_uses_fallback_on_exception() -> None:
    doc, fallback = _run_fallback(_PrimaryExceptionParser)
    assert fallback is not None
    assert isinstance(doc, _DummyDoc)
    assert doc.get_markdown() == "fallback content"
    assert fallback._called is True

