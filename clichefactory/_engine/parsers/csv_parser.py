from __future__ import annotations

import csv
from io import StringIO
from typing import List, Optional, Sequence, Tuple

from clichefactory._engine.adapters.csv_adapter import CsvNormalizedDoc
from clichefactory._engine.models.document_model import Block, Heading, Table, TableCell
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser


def _safe_decode(content: bytes) -> str:
    """
    Decode bytes to text with a couple of pragmatic fallbacks.
    """
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort: replace undecodable bytes
    return content.decode("utf-8", errors="replace")


def _sample_text(text: str, max_chars: int = 32_000, max_lines: int = 200) -> str:
    """
    Return a prefix of the text limited by characters and lines for sniffing.
    """
    if len(text) > max_chars:
        text = text[:max_chars]
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return "\n".join(lines)


def _sniff_dialect(sample: str) -> Tuple[csv.Dialect, bool]:
    """
    Try csv.Sniffer to detect dialect and header. Fall back to a simple heuristic.
    Returns (dialect, has_header_guess).
    """
    sniffer = csv.Sniffer()
    candidates = [",", ";", "\t", "|"]

    try:
        dialect = sniffer.sniff(sample, delimiters="".join(candidates))
        has_header = False
        try:
            has_header = sniffer.has_header(sample)
        except csv.Error:
            has_header = False
        return dialect, has_header
    except csv.Error:
        pass

    # Manual heuristic when Sniffer fails
    lines = [ln for ln in sample.splitlines() if ln.strip()]
    best_delim = ","
    best_score = -1.0
    best_cols = 1

    for delim in candidates:
        counts: List[int] = []
        for ln in lines:
            parts = ln.split(delim)
            counts.append(len(parts))
        if not counts:
            continue
        # Score: prefer stable column count across lines and more columns
        from collections import Counter

        counter = Counter(counts)
        most_common_cols, freq = counter.most_common(1)[0]
        ratio = freq / len(counts)
        score = ratio * most_common_cols
        if most_common_cols <= 1:
            continue
        if score > best_score:
            best_score = score
            best_delim = delim
            best_cols = most_common_cols

    class _Fallback(csv.Dialect):
        delimiter = best_delim
        quotechar = '"'
        doublequote = True
        skipinitialspace = True
        lineterminator = "\n"
        quoting = csv.QUOTE_MINIMAL

    # Very rough header guess: use first two non-empty lines if available
    has_header = False
    if len(lines) >= 2:
        first = lines[0].split(best_delim)
        second = lines[1].split(best_delim)
        if len(first) == len(second) == best_cols:
            # If second row is more numeric-ish, first is likely header
            def num_like(vals: Sequence[str]) -> int:
                c = 0
                for v in vals:
                    v = v.strip()
                    if not v:
                        continue
                    try:
                        float(v.replace(",", "."))
                        c += 1
                    except ValueError:
                        continue
                return c

            has_header = num_like(second) > num_like(first)

    return _Fallback(), has_header


def _build_markdown_from_rows(rows: List[List[str]], has_header: bool) -> str:
    if not rows:
        return ""

    def md_row(cols: List[str]) -> str:
        safe = [c.replace("\n", " ").strip() for c in cols]
        return "| " + " | ".join(safe) + " |"

    header = rows[0] if rows else []
    body = rows[1:] if has_header and len(rows) > 1 else rows[1:] if has_header else rows

    if not header:
        return ""

    lines: List[str] = []
    lines.append(md_row(header))
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for r in body:
        lines.append(md_row(r))
    return "\n".join(lines)


def _build_table_from_rows(rows: List[List[str]], has_header: bool) -> Table:
    cells: List[TableCell] = []
    if not rows:
        return Table(cells=tuple(), bbox=None)

    start_data_row = 1 if has_header else 0

    if has_header:
        for j, txt in enumerate(rows[0]):
            cells.append(TableCell(text=txt, row=0, col=j, bbox=None))
    else:
        # Synthesize a header row for structural completeness
        max_cols = max(len(r) for r in rows) if rows else 0
        for j in range(max_cols):
            cells.append(TableCell(text=f"col_{j}", row=0, col=j, bbox=None))

    for i, row_vals in enumerate(rows[start_data_row:], start=start_data_row):
        for j, txt in enumerate(row_vals):
            cells.append(TableCell(text=txt, row=i, col=j, bbox=None))

    return Table(cells=tuple(cells), bbox=None)


class CsvParser(MediaParser):
    """
    CSV -> Table -> CsvNormalizedDoc
    """

    def __init__(self, cacher=None, **kwargs) -> None:
        super().__init__(cacher=cacher, **kwargs)

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        text = _safe_decode(content)
        sample = _sample_text(text)
        dialect, has_header = _sniff_dialect(sample)

        reader = csv.reader(StringIO(text), dialect=dialect)
        rows: List[List[str]] = [list(r) for r in reader]

        if not rows:
            blocks: List[Block] = [Heading(level=1, text=filename or "CSV")]
            markdown = f"# {filename or 'CSV'}\n\n_Empty CSV file_\n"
            return CsvNormalizedDoc(filename=filename, blocks=blocks, markdown=markdown)

        # Normalize row lengths to the maximum number of columns for table consistency
        max_cols = max(len(r) for r in rows)
        norm_rows: List[List[str]] = []
        for r in rows:
            if len(r) < max_cols:
                r = r + [""] * (max_cols - len(r))
            norm_rows.append(r)

        markdown_table = _build_markdown_from_rows(norm_rows, has_header=has_header)
        table_block = _build_table_from_rows(norm_rows, has_header=has_header)

        title = (filename.rsplit(".", 1)[0] if filename else "CSV").strip() or "CSV"
        blocks: List[Block] = [Heading(level=1, text=title), table_block]

        markdown_lines: List[str] = [f"# {title}"]
        if markdown_table:
            markdown_lines.append("")
            markdown_lines.append(markdown_table)
        markdown = "\n".join(markdown_lines).strip() + "\n"

        return CsvNormalizedDoc(filename=filename, blocks=blocks, markdown=markdown)

