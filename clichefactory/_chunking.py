"""Chunk strategies for long-document extraction.

A ``ChunkStrategy`` takes a markdown string (plus optional meta) and returns
an ordered list of :class:`~clichefactory.types.Chunk` objects.  The public
re-exports live in :mod:`clichefactory.chunking`.

Design goals:

- Deterministic: same input → same chunks.
- Boundary-aware: prefer to split on paragraph / heading / page boundaries.
- Overlap-capable: allow a configurable number of pages (or tokens) of
  overlap so scalar fields near a chunk boundary are seen twice and resolve
  cleanly.
- Dep-light: no ``tiktoken``; token counts use a simple char-based
  approximation (``chars / 4``).  Good enough for chunk sizing — we do not
  need precise token accounting here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from clichefactory.types import Chunk


# ── Protocol ──────────────────────────────────────────────────────────────


class ChunkStrategy(Protocol):
    """Split a markdown document into ordered chunks.

    Implementations may be sync or async.  ``chunks`` is awaited by the
    orchestrator, so returning a plain ``list[Chunk]`` (not a coroutine) is
    fine as long as the method itself is declared ``async def``.
    """

    async def chunks(self, markdown: str, meta: dict[str, Any] | None = None) -> list[Chunk]: ...


# ── Token approximation ───────────────────────────────────────────────────

_CHARS_PER_TOKEN = 4
"""Rough chars-per-token ratio for English-ish text.  We deliberately avoid
pulling in ``tiktoken`` — chunk sizing does not need to be exact, and the
extractor will truncate server-side if anything overflows."""


def _approx_tokens(s: str) -> int:
    return max(1, len(s) // _CHARS_PER_TOKEN)


# ── Page markers ──────────────────────────────────────────────────────────
# Supported page-marker forms (match order matters — most specific first).
# If no marker is present, ``PageChunker`` falls back to token-based splitting
# and emits a warning via the orchestrator.
_PAGE_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    # ClicheFactory canonical form — to be emitted by to_markdown going
    # forward.  Kept first so it wins once converters emit it.
    re.compile(r"<!--\s*cf:page\s+(\d+)\s*-->", re.IGNORECASE),
    # Docling / generic HTML comment form.
    re.compile(r"<!--\s*page\s*[:=]?\s*(\d+)\s*-->", re.IGNORECASE),
    # Bracketed form sometimes seen in VLM output.
    re.compile(r"^\s*\[\s*page\s*(\d+)\s*\]\s*$", re.IGNORECASE | re.MULTILINE),
    # Plain "Page N" on its own line.
    re.compile(r"^\s*page\s+(\d+)\s*$", re.IGNORECASE | re.MULTILINE),
)


def _find_page_breaks(markdown: str) -> list[tuple[int, int]]:
    """Return ordered list of ``(page_number, char_offset)`` page breaks.

    The ``char_offset`` is the position where page ``N`` begins.  A final
    sentinel is *not* appended; callers should treat the end of the string
    as the end of the last page.  Returns ``[]`` if no markers are found.
    """
    hits: list[tuple[int, int]] = []
    seen_pages: set[int] = set()
    for pat in _PAGE_MARKER_PATTERNS:
        for m in pat.finditer(markdown):
            try:
                pn = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if pn in seen_pages:
                continue
            seen_pages.add(pn)
            hits.append((pn, m.start()))
    hits.sort(key=lambda t: t[1])
    return hits


# ── Boundary-finding helpers ──────────────────────────────────────────────

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def _snap_to_paragraph_boundary(markdown: str, pos: int, *, search_back: int = 400) -> int:
    """Move ``pos`` left to the nearest blank-line boundary.

    If no blank line is found within ``search_back`` chars, returns ``pos``
    unchanged (we won't sacrifice too much content to snap).
    """
    if pos <= 0 or pos >= len(markdown):
        return max(0, min(pos, len(markdown)))
    window_start = max(0, pos - search_back)
    window = markdown[window_start:pos]
    matches = list(_PARAGRAPH_BREAK.finditer(window))
    if not matches:
        return pos
    return window_start + matches[-1].end()


# ── Implementations ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TokenChunker:
    """Split markdown into roughly equal token-sized chunks.

    Splits on paragraph boundaries when possible.  This is the default
    chunker because it has no preconditions on input format.

    Parameters
    ----------
    max_tokens:
        Target size of each chunk, in approximate tokens (char/4).  Default
        ``12_000`` is a safe fit for an 8k-ish prompt budget once the system
        prompt and schema are added.
    overlap_tokens:
        Number of tokens to repeat at the start of each subsequent chunk.
        Prevents fields near a boundary from being split across chunks.
        Default ``400``.
    """

    max_tokens: int = 12_000
    overlap_tokens: int = 400

    async def chunks(self, markdown: str, meta: dict[str, Any] | None = None) -> list[Chunk]:
        if not markdown:
            return []
        max_chars = self.max_tokens * _CHARS_PER_TOKEN
        overlap_chars = max(0, self.overlap_tokens * _CHARS_PER_TOKEN)
        if len(markdown) <= max_chars:
            return [
                Chunk(
                    index=0,
                    text=markdown,
                    char_start=0,
                    char_end=len(markdown),
                )
            ]
        out: list[Chunk] = []
        pos = 0
        i = 0
        while pos < len(markdown):
            end = min(len(markdown), pos + max_chars)
            if end < len(markdown):
                end = _snap_to_paragraph_boundary(markdown, end)
                if end <= pos:
                    end = min(len(markdown), pos + max_chars)
            out.append(
                Chunk(
                    index=i,
                    text=markdown[pos:end],
                    char_start=pos,
                    char_end=end,
                )
            )
            if end >= len(markdown):
                break
            next_pos = max(pos + 1, end - overlap_chars)
            pos = next_pos
            i += 1
        return out


@dataclass(frozen=True, slots=True)
class PageChunker:
    """Group consecutive pages into chunks.

    Requires the markdown to contain page markers (see ``_PAGE_MARKER_PATTERNS``).
    If no markers are found, falls back to :class:`TokenChunker` with
    equivalent-ish sizing — the orchestrator will emit a warning when this
    happens.

    Parameters
    ----------
    pages_per_chunk:
        How many pages each chunk should cover.  Default ``15``.
    overlap_pages:
        How many trailing pages from the previous chunk to repeat at the
        start of the next.  Default ``1``.
    """

    pages_per_chunk: int = 15
    overlap_pages: int = 1

    async def chunks(self, markdown: str, meta: dict[str, Any] | None = None) -> list[Chunk]:
        if not markdown:
            return []
        breaks = _find_page_breaks(markdown)
        if not breaks:
            # Fallback — approximate by token size.  The orchestrator is
            # responsible for warning the caller; here we just produce
            # reasonable chunks so the pipeline continues.
            fallback = TokenChunker(max_tokens=self.pages_per_chunk * 1500)
            return await fallback.chunks(markdown, meta)

        page_starts: list[tuple[int, int]] = list(breaks)
        page_starts.sort(key=lambda t: t[0])

        out: list[Chunk] = []
        stride = max(1, self.pages_per_chunk - max(0, self.overlap_pages))
        chunk_index = 0
        i = 0
        while i < len(page_starts):
            page_start_num, char_start = page_starts[i]
            j_end = min(len(page_starts), i + self.pages_per_chunk)
            page_end_num = page_starts[j_end - 1][0]
            if j_end < len(page_starts):
                char_end = page_starts[j_end][1]
            else:
                char_end = len(markdown)
            text = markdown[char_start:char_end]
            out.append(
                Chunk(
                    index=chunk_index,
                    text=text,
                    page_start=page_start_num,
                    page_end=page_end_num,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
            chunk_index += 1
            if j_end >= len(page_starts):
                break
            i += stride
        return out


@dataclass(frozen=True, slots=True)
class HeadingChunker:
    """Split markdown at headings of a given level or higher.

    Chunks are bounded by lines matching ``^#{1,min_heading_level} ``.
    If a single section exceeds ``max_tokens``, it is re-split by
    :class:`TokenChunker` to stay within budget.

    Parameters
    ----------
    max_tokens:
        Soft cap per chunk.  Sections larger than this are re-split.
    min_heading_level:
        Split on ``#`` through ``#`` × ``min_heading_level``.  Default ``2``
        (split on H1 and H2, keep H3+ inside their parent chunk).
    """

    max_tokens: int = 12_000
    min_heading_level: int = 2

    async def chunks(self, markdown: str, meta: dict[str, Any] | None = None) -> list[Chunk]:
        if not markdown:
            return []
        level_class = "#" * max(1, self.min_heading_level)
        pat = re.compile(
            rf"^(#{{1,{len(level_class)}}})\s+(.+?)\s*$",
            re.MULTILINE,
        )
        starts: list[tuple[int, tuple[str, ...]]] = []
        heading_path: list[str] = []
        for m in pat.finditer(markdown):
            hashes, title = m.group(1), m.group(2).strip()
            depth = len(hashes)
            heading_path = heading_path[: depth - 1]
            heading_path.append(title)
            starts.append((m.start(), tuple(heading_path)))
        if not starts:
            return await TokenChunker(max_tokens=self.max_tokens).chunks(markdown, meta)

        raw_sections: list[tuple[int, int, tuple[str, ...]]] = []
        if starts[0][0] > 0:
            raw_sections.append((0, starts[0][0], ()))
        for k, (s, path) in enumerate(starts):
            end = starts[k + 1][0] if k + 1 < len(starts) else len(markdown)
            raw_sections.append((s, end, path))

        max_chars = self.max_tokens * _CHARS_PER_TOKEN
        out: list[Chunk] = []
        idx = 0
        for s, e, path in raw_sections:
            text = markdown[s:e]
            if not text.strip():
                continue
            if len(text) <= max_chars:
                out.append(
                    Chunk(
                        index=idx,
                        text=text,
                        heading_path=path,
                        char_start=s,
                        char_end=e,
                    )
                )
                idx += 1
                continue
            # Section is too big — re-split.
            sub = await TokenChunker(max_tokens=self.max_tokens).chunks(text)
            for sc in sub:
                out.append(
                    Chunk(
                        index=idx,
                        text=sc.text,
                        heading_path=path,
                        char_start=(s + (sc.char_start or 0)),
                        char_end=(s + (sc.char_end or len(sc.text))),
                    )
                )
                idx += 1
        return out
