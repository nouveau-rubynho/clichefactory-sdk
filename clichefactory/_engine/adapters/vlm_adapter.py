"""
NormalizedDoc adapter for markdown-based pipelines (VLM, OCR LLM, layout parsers, etc.).
Uses per-page markdown structure; single-page documents use [(1, None, markdown)].
"""
from __future__ import annotations

import re
from typing import Sequence

from clichefactory._engine.models.document_model import Heading, Image, Page, Paragraph, Section, Table
from clichefactory._engine.models.normalized_doc import NormalizedDoc

# Per-page data: (page_index, size_tuple | None, markdown_str)
PageMarkdownItem = tuple[int, tuple[float, float] | None, str]


def _markdown_to_plain_text(markdown: str) -> str:
    """Light markdown stripping for get_plain_text."""
    text = markdown
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^\s*\|", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


class VlmNormalizedDoc(NormalizedDoc):
    """
    NormalizedDoc built from per-page markdown.
    Used by docling_vlm, ocr_llm, pymupdf, yolo_per_partes, and image parsers.
    Single-page documents (e.g. image OCR) use [(1, None, markdown)].
    """

    def __init__(self, page_items: Sequence[PageMarkdownItem]) -> None:
        """
        :param page_items: List of (page_index, size_tuple|None, markdown_str) in page order.
        """
        self._page_items = list(page_items)
        self._markdown = "\n\n".join(md for _idx, _size, md in self._page_items)
        self._plain_text = _markdown_to_plain_text(self._markdown)

        # Build pages: one Page per item with a single Paragraph block
        pages: list[Page] = []
        all_blocks: list[Paragraph] = []
        for idx, size, md in self._page_items:
            blocks = (Paragraph(text=md),)
            pages.append(Page(index=idx, size=size, blocks=blocks))
            all_blocks.append(Paragraph(text=md))

        self.pages = tuple(pages)
        self.sections = (
            Section(
                heading=Heading(level=1, text="Document"),
                blocks=tuple(all_blocks),
                subsections=(),
            ),
        )
        self.images: Sequence[Image] = ()
        self.tables: Sequence[Table] = ()

    def get_plain_text(self) -> str:
        return self._plain_text

    def get_markdown(self) -> str:
        return self._markdown
