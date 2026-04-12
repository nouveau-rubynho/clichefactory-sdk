from __future__ import annotations

import io
import logging
import pikepdf
from pypdf import PdfReader, PdfWriter  
from pypdf.generic import NameObject, ArrayObject, FloatObject 

logger = logging.getLogger(__name__)


def _fix_missing_mediabox(pdf_bytes: bytes) -> bytes:
    """
    Inject a standard A4 MediaBox into pages that lack explicit dimensions.

    This is a targeted repair for malformed PDFs where /Page entries are
    missing /MediaBox (and Docling / renderers fail because page size
    cannot be resolved). On success, returns new bytes; on failure or when
    no changes are needed, returns the original bytes unchanged.
    """
    if PdfReader is None or PdfWriter is None or NameObject is None:
        # pypdf is not available; nothing to do.
        return pdf_bytes

    try:
        logger.info("Attempting targeted MediaBox repair via pypdf.")
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)

        modified = False
        fixed_pages = 0
        for page in writer.pages:
            # If the page dictionary does not have a MediaBox key, inject A4.
            if "/MediaBox" not in page:
                # Standard A4 size in points: [0, 0, 595.28, 841.89]
                page[NameObject("/MediaBox")] = ArrayObject(
                    [
                        FloatObject(0),
                        FloatObject(0),
                        FloatObject(595.28),
                        FloatObject(841.89),
                    ]
                )
                modified = True
                fixed_pages += 1

        if not modified:
            logger.info("MediaBox repair: no pages required fixing.")
            return pdf_bytes

        out_io = io.BytesIO()
        writer.write(out_io)
        logger.info("MediaBox repair succeeded; injected A4 MediaBox into %d page(s).", fixed_pages)
        return out_io.getvalue()
    except Exception as e:  # pragma: no cover - defensive; falls back to original bytes.
        logger.error("Failed to repair missing MediaBox via pypdf: %s", e)
        return pdf_bytes


def repair_pdf_bytes(content: bytes) -> bytes:
    """
    Attempt to normalize/repair a PDF byte stream.

    Strategy (best-effort, non-destructive):
    1. First attempt a targeted MediaBox fix using pypdf for pages that
       lack explicit dimensions (injecting a default A4 MediaBox).
    2. Then, if pikepdf is available, run a structural repair pass using
       QPDF (via pikepdf) on the possibly already-repaired bytes.

    On success, returns new PDF bytes with a cleaned object tree, resolved
    page attributes, and fixed cross-references. On failure (or when
    neither repair step can change anything), returns the original bytes
    unchanged.
    """
    original = content

    # Step 1: targeted MediaBox repair (non-fatal; returns original on failure).
    try:
        after_mediabox = _fix_missing_mediabox(content)
    except Exception as e:  # pragma: no cover - very defensive
        logger.error("Unexpected error during MediaBox repair: %s", e)
        after_mediabox = content

    # Step 2: structural repair via pikepdf/QPDF, if available.
    if pikepdf is None:
        if after_mediabox is not original:
            # We at least managed to repair MediaBox; return those bytes.
            return after_mediabox
        logger.warning("pikepdf is not installed; skipping structural PDF repair.")
        return original

    try:
        with pikepdf.open(io.BytesIO(after_mediabox)) as pdf:  # type: ignore[attr-defined]
            out = io.BytesIO()
            pdf.save(out)
            return out.getvalue()
    except Exception as e:
        logger.warning("Failed to repair PDF structure via pikepdf: %s", e)
        # Fall back to the best we had so far (possibly already MediaBox-fixed bytes).
        return after_mediabox

