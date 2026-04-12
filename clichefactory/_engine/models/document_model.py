from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Optional, Union, Tuple


BBox = Tuple[float, float, float, float]  # (x0, y0, x1, y1)

# ---------- Document Layout Model ----------
@dataclass(frozen=True)
class Page:
    index: int
    size: Optional[Tuple[float, float]]  # width, height
    blocks: Sequence[Block]

@dataclass(frozen=True)
class Paragraph:
    text: str
    bbox: Optional[BBox] = None

@dataclass(frozen=True)
class TableCell:
    text: str
    row: int
    col: int
    bbox: Optional[BBox] = None

@dataclass(frozen=True)
class Table:
    cells: Sequence[TableCell]
    bbox: Optional[BBox] = None

@dataclass(frozen=True)
class Image:
    ref: str               # opaque reference (id, URI, etc.)
    mime_type: str
    bbox: Optional[BBox] = None
    alt_text: Optional[str] = None

@dataclass(frozen=True)
class Heading:
    level: int          # 1 = H1, 2 = H2, etc.
    text: str
    bbox: Optional[BBox] = None

Block = Union[Heading, Paragraph, Table, Image]  # Just alias for type checkers

# ---------- Document Semantic Model ----------
@dataclass(frozen=True)
class Section:
    heading: Heading
    blocks: Sequence[Block]
    subsections: Sequence[Section]
