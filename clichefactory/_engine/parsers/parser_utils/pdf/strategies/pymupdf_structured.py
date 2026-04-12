"""
PyMuPDF structured PDF strategy: extract native text with layout preserved.
Uses get_text("dict", sort=True) for reading order; builds markdown with headers/tables.
"""
from __future__ import annotations

import fitz

from clichefactory._engine.adapters.vlm_adapter import PageMarkdownItem, VlmNormalizedDoc
from clichefactory._engine.models.normalized_doc import NormalizedDoc

# Ligatures and stray glyphs to clean
_LIGATURE_MAP = {
    "\uf0b7": "*",  # bullet
    "\uf0a7": "§",
    "\uf0b0": "°",
    "\uf0b1": "±",
    "\uf0b2": "²",
    "\uf0b3": "³",
    "\uf0ae": "®",
    "\uf0a9": "©",
    "\uf0a2": "¢",
    "\uf0a3": "£",
    "\uf0a5": "¥",
    "\uf0b6": "¶",
    "\uf0b4": "´",
    "\uf0b5": "µ",
}


def _clean_text(text: str) -> str:
    """Replace ligatures and stray glyphs."""
    for old, new in _LIGATURE_MAP.items():
        text = text.replace(old, new)
    return text


def _blocks_to_markdown(blocks: list) -> str:
    """
    Convert PyMuPDF dict blocks to markdown.
    Preserves reading order (blocks sorted by y0, x0).
    Uses font size heuristics for headers.
    """
    lines_out: list[str] = []
    font_sizes: list[float] = []

    for block in blocks:
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                if size > 0:
                    font_sizes.append(size)

    median_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 12.0
    header_threshold = median_size * 1.25

    for block in blocks:
        if block.get("type") != 0:
            continue

        block_lines: list[str] = []
        for line in block.get("lines", []):
            line_text_parts: list[str] = []
            line_is_header = False
            for span in line.get("spans", []):
                txt = _clean_text(span.get("text", ""))
                if not txt:
                    continue
                size = span.get("size", 0)
                if size >= header_threshold and len(txt.strip()) < 80:
                    line_is_header = True
                line_text_parts.append(txt)
            if line_text_parts:
                full_line = " ".join(line_text_parts).strip()
                if line_is_header:
                    block_lines.append(f"## {full_line}")
                else:
                    block_lines.append(full_line)

        if block_lines:
            lines_out.append("\n".join(block_lines))

    return "\n\n".join(lines_out)


class PymupdfStructuredStrategy:
    """
    Extract text from structured PDFs using PyMuPDF.
    Preserves layout via dict/blocks; outputs LLM-ready markdown.
    """

    def parse(self, content: bytes, filename: str) -> NormalizedDoc:
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            parts: list[str] = []
            for i, page in enumerate(doc):
                page_num = i + 1
                dict_data = page.get_text("dict", sort=True)
                blocks = dict_data.get("blocks", [])
                md = _blocks_to_markdown(blocks)
                if md.strip():
                    parts.append(f"## Page {page_num}\n\n{md}")
                else:
                    text_fallback = page.get_text("text", sort=True).strip()
                    if text_fallback:
                        parts.append(f"## Page {page_num}\n\n{_clean_text(text_fallback)}")
                    else:
                        parts.append(f"## Page {page_num}\n\n[No text on this page]")

            page_items: list[PageMarkdownItem] = [
                (i + 1, None, part) for i, part in enumerate(parts)
            ]
            return VlmNormalizedDoc(page_items)
        finally:
            doc.close()
