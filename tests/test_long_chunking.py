"""Unit tests for chunk strategies."""
from __future__ import annotations

import asyncio

import pytest

from clichefactory.chunking import HeadingChunker, PageChunker, TokenChunker


def _run(coro):
    return asyncio.run(coro)


# ── TokenChunker ──────────────────────────────────────────────────────────


def test_token_chunker_short_doc_single_chunk():
    doc = "Hello world.\n\nAnother paragraph."
    chunks = _run(TokenChunker(max_tokens=1000).chunks(doc))
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == doc
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(doc)
    assert chunks[0].page_start is None


def test_token_chunker_empty_string_returns_no_chunks():
    assert _run(TokenChunker().chunks("")) == []


def test_token_chunker_splits_at_paragraph_boundaries():
    # Build a doc with a few paragraphs, force small chunk size.
    paras = [f"Paragraph {i}. " + ("x" * 200) for i in range(10)]
    doc = "\n\n".join(paras)
    chunks = _run(TokenChunker(max_tokens=200, overlap_tokens=20).chunks(doc))
    assert len(chunks) > 1
    # Every chunk should be non-empty
    assert all(c.text for c in chunks)
    # Chunks are index-ordered
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # Consecutive chunks overlap (chunks 0 ends after chunk 1 starts)
    for prev, cur in zip(chunks, chunks[1:]):
        assert cur.char_start is not None and prev.char_end is not None
        assert cur.char_start <= prev.char_end


def test_token_chunker_covers_full_document():
    doc = "A" * 10_000
    chunks = _run(TokenChunker(max_tokens=500, overlap_tokens=50).chunks(doc))
    # Concatenating the unique parts should recover the full doc (roughly).
    # Simpler check: last chunk ends at end of doc, first starts at 0.
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(doc)


# ── PageChunker ───────────────────────────────────────────────────────────


def _build_paged_markdown(num_pages: int, marker_fmt: str = "<!-- cf:page {n} -->") -> str:
    parts: list[str] = []
    for n in range(1, num_pages + 1):
        parts.append(marker_fmt.format(n=n))
        parts.append(f"\n\nContent of page {n}.\n\n" + ("lorem " * 50))
    return "\n".join(parts)


def test_page_chunker_groups_by_page_with_cf_markers():
    doc = _build_paged_markdown(10)
    chunks = _run(PageChunker(pages_per_chunk=3, overlap_pages=0).chunks(doc))
    assert len(chunks) == 4  # 3+3+3+1
    assert chunks[0].page_start == 1 and chunks[0].page_end == 3
    assert chunks[1].page_start == 4 and chunks[1].page_end == 6
    assert chunks[2].page_start == 7 and chunks[2].page_end == 9
    assert chunks[3].page_start == 10 and chunks[3].page_end == 10


def test_page_chunker_respects_overlap():
    doc = _build_paged_markdown(10)
    chunks = _run(PageChunker(pages_per_chunk=4, overlap_pages=1).chunks(doc))
    # stride = 4 - 1 = 3; chunks at pages 1-4, 4-7, 7-10
    starts = [c.page_start for c in chunks]
    assert starts == [1, 4, 7]
    ends = [c.page_end for c in chunks]
    assert ends == [4, 7, 10]


def test_page_chunker_supports_legacy_page_marker():
    doc = "\n".join(
        [f"<!-- page: {n} -->\n\nContent {n}" for n in range(1, 5)]
    )
    chunks = _run(PageChunker(pages_per_chunk=2, overlap_pages=0).chunks(doc))
    assert len(chunks) == 2
    assert chunks[0].page_start == 1 and chunks[0].page_end == 2


def test_page_chunker_falls_back_when_no_markers():
    doc = "lorem " * 1000  # no page markers
    chunks = _run(PageChunker(pages_per_chunk=2, overlap_pages=0).chunks(doc))
    # Non-empty output; page_start/page_end unset.
    assert len(chunks) >= 1
    assert all(c.page_start is None for c in chunks)


# ── HeadingChunker ────────────────────────────────────────────────────────


def test_heading_chunker_splits_on_h1_and_h2():
    doc = (
        "# Intro\n\n"
        + "Some intro text.\n\n"
        + "## Section A\n\n"
        + "Body A.\n\n"
        + "## Section B\n\n"
        + "Body B.\n\n"
        + "# Conclusion\n\n"
        + "Wrap-up.\n"
    )
    chunks = _run(HeadingChunker(max_tokens=1000, min_heading_level=2).chunks(doc))
    # We expect a chunk per heading boundary: Intro, Section A, Section B, Conclusion.
    titles = [c.heading_path for c in chunks]
    assert ("Intro",) in titles
    assert ("Intro", "Section A") in titles
    assert ("Intro", "Section B") in titles
    assert ("Conclusion",) in titles


def test_heading_chunker_resplits_oversize_sections():
    big = "x" * 50_000
    doc = f"# One\n\n{big}\n\n# Two\n\nSmall tail."
    chunks = _run(HeadingChunker(max_tokens=2000).chunks(doc))
    # The big section is forced to split into multiple chunks but all carry the H1 path.
    one_chunks = [c for c in chunks if c.heading_path == ("One",)]
    assert len(one_chunks) > 1


def test_heading_chunker_empty_doc():
    assert _run(HeadingChunker().chunks("")) == []


def test_heading_chunker_no_headings_falls_back_to_token():
    doc = "just a plain blob " * 500
    chunks = _run(HeadingChunker(max_tokens=500).chunks(doc))
    assert len(chunks) >= 1
    assert all(c.heading_path == () for c in chunks)
