from __future__ import annotations

from typing import Optional, Sequence, List, Tuple
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.models.document_model import Page, Section, Heading, Table, Block



class XlsxNormalizedDoc(NormalizedDoc):
    def __init__(self, filename: str, sheet_blocks: List[Block], markdown: str) -> None:
        self.filename = filename
        self.summary_text = ""  # TODO: Perhaps you want to implement some LLM descriptor here
        self.markdown = markdown

        # XLSX has no stable “page layout” for LLM processing — use a single synthetic page.
        self.pages = (Page(index=1, size=None, blocks=tuple(sheet_blocks)),)
        self.sections = self._build_sections_from_headings(self.pages[0].blocks)

        self.images = tuple()  # not extracting embedded images in this example
        self.tables = tuple(b for b in self.pages[0].blocks if isinstance(b, Table))


    def get_plain_text(self) -> str:
        # plain text = markdown without pipes could be done, but markdown is usually fine
        return self.get_markdown()

    def get_markdown(self) -> str:
        return self.markdown

    def get_json(self, table_index: int = 0, header: bool = True) -> Optional[list[dict[str, str]]]:
        """
        Convert the first table in this document to a list of row dicts.

        - If header=True: uses row 0 as header keys.
            - Missing/empty header cell => "col_{index}"
            - Duplicate header names are disambiguated with _1, _2, ... in left-to-right order.
            (e.g., ADDRESS, ADDRESS -> ADDRESS_1, ADDRESS_2)
        - If header=False: uses synthetic keys "col_{index}" and includes row 0 as data.
        """
        if not self.tables:
            return None

        t = self.tables[table_index]
        if not getattr(t, "cells", None):
            return None

        # Build a row->col->text matrix
        max_row = max(c.row for c in t.cells)
        max_col = max(c.col for c in t.cells)

        grid: list[list[str]] = [[""] * (max_col + 1) for _ in range(max_row + 1)]
        for c in t.cells:
            if 0 <= c.row <= max_row and 0 <= c.col <= max_col:
                grid[c.row][c.col] = (c.text or "").strip()

        def make_unique_header(raw_keys: list[str]) -> list[str]:
            # First pass: normalize empties and count occurrences
            base_keys: list[str] = []
            counts: dict[str, int] = {}
            for j, k in enumerate(raw_keys):
                base = (k or "").strip()
                if not base:
                    base = f"col_{j}"
                base_keys.append(base)
                counts[base] = counts.get(base, 0) + 1

            # Second pass: disambiguate duplicates with _1, _2, ...
            seen: dict[str, int] = {}
            unique: list[str] = []
            for base in base_keys:
                if counts.get(base, 0) > 1:
                    seen[base] = seen.get(base, 0) + 1
                    unique.append(f"{base}_{seen[base]}")
                else:
                    unique.append(base)
            return unique

        if header and grid:
            raw_header = grid[0]
            keys = make_unique_header(raw_header)
            start_row = 1
        else:
            keys = [f"col_{j}" for j in range(max_col + 1)]
            start_row = 0

        out: list[dict[str, str]] = []
        for r in range(start_row, max_row + 1):
            row_vals = grid[r]
            if all(not (v or "").strip() for v in row_vals):
                continue
            out.append({keys[j]: (row_vals[j] or "") for j in range(len(keys))})

        return out


    def _build_sections_from_headings(self, blocks: Sequence[Block]) -> Sequence[Section]:
        # reuse your exact logic (simplified copy)
        class _Builder:
            def __init__(self, heading: Heading) -> None:
                self.heading = heading
                self.blocks: list[Block] = []
                self.children: list[Section] = []

            def finalize(self) -> Section:
                return Section(heading=self.heading, blocks=tuple(self.blocks), subsections=tuple(self.children))

        stack: list[Tuple[int, _Builder]] = []
        roots: list[Section] = []

        def push_section(h: Heading) -> None:
            nonlocal stack, roots
            b = _Builder(h)
            lvl = max(1, int(h.level))
            while stack and stack[-1][0] >= lvl:
                _, closed = stack.pop()
                sec = closed.finalize()
                if stack:
                    stack[-1][1].children.append(sec)
                else:
                    roots.append(sec)
            stack.append((lvl, b))

        def add_to_current(block: Block) -> None:
            if not stack:
                push_section(Heading(level=1, text="Document"))
            stack[-1][1].blocks.append(block)

        for blk in blocks:
            if isinstance(blk, Heading):
                push_section(blk)
            else:
                add_to_current(blk)

        while stack:
            _, b = stack.pop()
            sec = b.finalize()
            if stack:
                stack[-1][1].children.append(sec)
            else:
                roots.append(sec)

        return tuple(roots)
