"""Regression tests for MediaParserRegistry parser instantiation.

``MediaParserRegistry.create_parser`` forwards ``media_parser_registry=self``
to every parser constructor. Each registered parser must accept that kwarg
(or absorb it via ``**kwargs``) — otherwise instantiation raises
``TypeError`` at parse time, the parser pipeline bails out, and any
fallback path that ships raw bytes at a multimodal LLM will reject the
file with an unsupported-MIME 400.
"""
from __future__ import annotations

from clichefactory._engine.parsers.csv_parser import CsvParser
from clichefactory._engine.parsers.docx_parser import DocxParser
from clichefactory._engine.parsers.media_parser_registry import (
    MediaParserRegistry,
)
from clichefactory._engine.parsers.text_parser import TextParser
from clichefactory._engine.parsers.xlsx_parser import XlsxParser


def _registry_with(ext: str, parser_cls) -> MediaParserRegistry:
    registry = MediaParserRegistry()
    registry.register(ext, parser_cls)
    return registry


def test_create_parser_instantiates_xlsx_via_registry() -> None:
    registry = _registry_with(".xlsx", XlsxParser)
    parser = registry.create_parser(".xlsx")
    assert isinstance(parser, XlsxParser)


def test_create_parser_instantiates_docx_via_registry() -> None:
    registry = _registry_with(".docx", DocxParser)
    parser = registry.create_parser(".docx")
    assert isinstance(parser, DocxParser)


def test_create_parser_instantiates_csv_via_registry() -> None:
    # Sanity check that the parsers that already accepted the kwarg
    # still round-trip cleanly through the registry.
    registry = _registry_with(".csv", CsvParser)
    parser = registry.create_parser(".csv")
    assert isinstance(parser, CsvParser)


def test_create_parser_instantiates_text_via_registry() -> None:
    registry = _registry_with(".txt", TextParser)
    parser = registry.create_parser(".txt")
    assert isinstance(parser, TextParser)
