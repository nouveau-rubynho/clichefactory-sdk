from __future__ import annotations

from typing import Any

import types as _types

from clichefactory._engine.parsers.parser_utils.pdf.docling_helpers import (
    extract_table_context_snippet,
    item_to_text,
)


class _DummyProv:
    def __init__(self, page_no: int) -> None:
        self.page_no = page_no


class _DummyItem:
    def __init__(self, text: str, page_no: int) -> None:
        self.text = text
        self.prov = [_DummyProv(page_no)]


class _DummyTableItem:
    def __init__(self, page_no: int) -> None:
        self.prov = [_DummyProv(page_no)]


class _DummyDoc:
    def __init__(self, sequence: list[tuple[Any, int]]) -> None:
        self._sequence = sequence

    def iterate_items(self, with_groups: bool = False):  # type: ignore[override]
        for item, _ in self._sequence:
            yield item, None


def test_item_to_text_basic() -> None:
    item = _DummyItem(" hello world ", page_no=1)
    assert item_to_text(item) == "hello world"


def _build_reading_order_for_test(sequence: list[tuple[Any, int]]) -> tuple[list, dict, dict]:
    """Build reading_order and table_index_map for test (bypasses DocItem check)."""
    reading_order: list = []
    table_index_map: dict = {}
    figure_index_map: dict = {}
    for i, (item, page_no) in enumerate(sequence):
        reading_order.append((item, page_no))
        if isinstance(item, _DummyTableItem):
            table_index_map[id(item)] = i
    return reading_order, table_index_map, figure_index_map


def test_build_reading_order_index_and_context_snippet_same_page() -> None:
    # Build a simple sequence: text, table, text on same page
    text_before = _DummyItem("Section before table", page_no=1)
    table = _DummyTableItem(page_no=1)
    text_after = _DummyItem("Section after table", page_no=1)
    doc = _DummyDoc([(text_before, 1), (table, 1), (text_after, 1)])

    reading_order, table_index_map, _ = _build_reading_order_for_test(
        [(text_before, 1), (table, 1), (text_after, 1)]
    )
    snippet = extract_table_context_snippet(
        doc, reading_order, table_index_map, table, window=2, max_chars=200
    )

    assert "Section before table" in snippet
    assert "Section after table" in snippet


def test_context_snippet_truncation() -> None:
    long_text = "word " * 200
    text_before = _DummyItem(long_text, page_no=1)
    table = _DummyTableItem(page_no=1)
    doc = _DummyDoc([(text_before, 1), (table, 1)])

    reading_order, table_index_map, _ = _build_reading_order_for_test(
        [(text_before, 1), (table, 1)]
    )
    snippet = extract_table_context_snippet(
        doc, reading_order, table_index_map, table, window=1, max_chars=100
    )

    assert len(snippet) <= 103  # 100 chars + optional "..."
    assert snippet.endswith("...")

