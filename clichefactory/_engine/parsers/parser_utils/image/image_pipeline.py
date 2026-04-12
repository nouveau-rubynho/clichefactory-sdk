"""
Image OCR pipeline: dispatches to engine-specific implementations.

Engines: pytesseract, rapidocr, easyocr, docling, ocr_llm.
"""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from clichefactory._engine.parsers.parser_utils.image.image_pipeline_options import ImagePipelineOptions

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from clichefactory._engine.ai_clients import AIClient


def _bytes_to_pil(content: bytes):
    """Load image bytes into PIL Image."""
    from PIL import Image

    return Image.open(io.BytesIO(content)).convert("RGB")


def _mime_from_filename(filename: str) -> str:
    """Infer MIME type from filename extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mime_map.get(ext, "image/png")


def run_ocr(
    content: bytes,
    filename: str,
    options: ImagePipelineOptions,
    *,
    ocr_client: "AIClient | None" = None,
) -> str:
    """
    Run OCR on image bytes.

    Returns:
        Extracted text as markdown/plain string.
    """
    engine = options.engine
    if engine == "pytesseract":
        return _run_pytesseract(content, options)
    if engine == "rapidocr":
        return _run_rapidocr(content, options)
    if engine == "easyocr":
        return _run_easyocr(content, options)
    if engine == "docling":
        return _run_docling_image(content, filename, options)
    if engine == "ocr_llm":
        return _run_ocr_llm(content, filename, options, ocr_client=ocr_client)
    raise ValueError(f"Unknown image OCR engine: {engine}")


def _run_pytesseract(content: bytes, options: ImagePipelineOptions) -> str:
    """OCR using pytesseract (Tesseract)."""
    import pytesseract

    img = _bytes_to_pil(content)
    lang = options.get_tesseract_lang()
    text = pytesseract.image_to_string(img, lang=lang)
    return (text or "").strip()


def _run_rapidocr(content: bytes, options: ImagePipelineOptions) -> str:
    """OCR using RapidOCR (ONNXRuntime backend) with language-aware model selection."""
    import numpy as np
    from rapidocr import RapidOCR

    img = _bytes_to_pil(content)
    arr = np.array(img)

    lang_script = options.get_rapidocr_lang()
    try:
        from rapidocr import LangRec
        lang_enum = LangRec(lang_script)
        engine = RapidOCR(params={"Rec.lang_type": lang_enum})
    except (ImportError, ValueError):
        engine = RapidOCR()

    result = engine(arr)
    if result is None:
        return ""
    word_results = getattr(result, "word_results", ())
    if not word_results:
        return ""
    texts = [str(w[0]) for w in word_results if w and w[0]]
    return "\n".join(texts).strip()


def _run_easyocr(content: bytes, options: ImagePipelineOptions) -> str:
    """
    OCR using EasyOCR.

    Note: EasyOCR loads per-language models; multi-language increases RAM usage.
    """
    import numpy as np

    try:
        import easyocr
    except ImportError:
        raise ImportError("easyocr is required for EasyOCR engine. Install with: pip install easyocr")

    img = _bytes_to_pil(content)
    arr = np.array(img)
    lang_list = options.get_easyocr_lang() or ["en"]
    reader = easyocr.Reader(lang_list)
    results = reader.readtext(arr)
    texts = [r[1] for r in results if len(r) > 1]
    return "\n".join(texts).strip()


def _run_docling_image(content: bytes, filename: str, options: ImagePipelineOptions) -> str:
    """OCR using Docling image pipeline."""
    from io import BytesIO

    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, ImageFormatOption
    from docling_core.types.io import DocumentStream

    converter = DocumentConverter(
        format_options={
            InputFormat.IMAGE: ImageFormatOption(),
        }
    )
    conversion_result = converter.convert(
        DocumentStream(name=filename, stream=BytesIO(content))
    )
    return conversion_result.document.export_to_markdown()


def _run_ocr_llm(
    content: bytes,
    filename: str,
    options: ImagePipelineOptions,
    *,
    ocr_client: "AIClient | None" = None,
) -> str:
    """OCR using AIClient (Gemini/OpenAI/Anthropic)."""
    from clichefactory._engine.ai_clients import SIMPLE_OCR_PROMPT

    if ocr_client is None:
        raise ValueError("ocr_client is required for ocr_llm engine")

    mime = _mime_from_filename(filename)
    return ocr_client.ocr(content, mime, SIMPLE_OCR_PROMPT.strip()) or ""
