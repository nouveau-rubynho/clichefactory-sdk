"""
PDF classifier: structured (native text) vs image (scanned).
Uses PyMuPDF for fast checks: text length, fonts, image coverage.
"""
from __future__ import annotations

from typing import Literal

import fitz


def classify_pdf(
    content: bytes,
    *,
    min_text_chars: int = 50,
    min_fonts: int = 1,
    image_coverage_threshold: float = 0.95,
) -> Literal["structured", "image"]:
    """
    Classify PDF as structured (native text, fonts) or image (scanned).

    - Structured: page has substantial text and fonts (digitally created).
    - Image: scanned PDF, little/no native text, or single image covers most of page.

    Returns "structured" if any page passes the nice-PDF checks; else "image".
    """
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        for page in doc:
            text = page.get_text().strip()
            fonts = page.get_fonts()

            # 1. Text length
            if len(text) < min_text_chars:
                continue

            # 2. Font presence (scanned PDFs usually have zero fonts)
            if len(fonts) < min_fonts:
                continue

            # 3. Image coverage: if single image covers > threshold of page, likely scan
            images = page.get_images(full=True)
            if images:
                rect = page.rect
                page_area = rect.width * rect.height
                for img_ref in images:
                    bbox = page.get_image_bbox(img_ref)
                    if bbox and not bbox.is_infinite:
                        img_area = bbox.width * bbox.height
                        if page_area > 0 and (img_area / page_area) >= image_coverage_threshold:
                            # Single image covers most of page -> image
                            continue
            # This page looks structured
            return "structured"

        return "image"
    finally:
        doc.close()
