"""
Shared Docling PdfPipeline and ImagePipeline options.

Configurable OCR engines: tesseract, rapidocr, easyocr.
RapidOCR tries to download FZYTK.TTF from modelscope.cn at runtime when font_path is not set;
that download often fails. Setting font_path to a local TTF avoids the download.
See: https://github.com/docling-project/docling-serve/issues/464
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    OcrEngine,
    PdfPipelineOptions,
    RapidOcrOptions,
    TableFormerMode,
    TesseractOcrOptions,
)


from clichefactory._engine.parsers.parser_utils.lang_mapping import (
    to_easyocr_list,
    to_tesseract_list,
)


def _resolve_ocr_font_path() -> str | None:
    """
    Resolve a local TTF path for RapidOCR so it does not try to download FZYTK.TTF.
    Uses DOCLING_OCR_FONT_PATH if set; else macOS Arial Unicode when available.
    """
    env_path = os.environ.get("DOCLING_OCR_FONT_PATH")
    if env_path and Path(env_path).is_file():
        return env_path
    if sys.platform == "darwin":
        arial_unicode = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
        if arial_unicode.is_file():
            return str(arial_unicode)
    return None


def get_pdf_pipeline_options(
    *,
    generate_page_images: bool = False,
    ocr_engine: Literal["tesseract", "rapidocr", "easyocr", "tesseract_sl_en"] = "tesseract",
    ocr_lang: str = "eng",
) -> PdfPipelineOptions:
    """
    Build PdfPipelineOptions for PDF parsing.

    ocr_engine: tesseract, rapidocr, or easyocr. "tesseract_sl_en" = tesseract with slv+eng.
    ocr_lang: engine-specific format (e.g. slv+eng for Tesseract).
    """
    if ocr_engine in ("tesseract", "tesseract_sl_en"):
        if ocr_engine == "tesseract_sl_en":
            ocr_lang = "slv+eng"
        lang_list = to_tesseract_list(ocr_lang)
        ocr_engine_enum = OcrEngine.TESSERACT
        ocr_options = TesseractOcrOptions(lang=lang_list)
    elif ocr_engine == "easyocr":
        lang_list = to_easyocr_list(ocr_lang)
        ocr_engine_enum = OcrEngine.EASYOCR
        ocr_options = EasyOcrOptions(lang=lang_list)
    else:
        font_path = _resolve_ocr_font_path()
        ocr_engine_enum = OcrEngine.RAPIDOCR
        ocr_options = RapidOcrOptions(lang=[], font_path=font_path)

    return PdfPipelineOptions(
        do_ocr=True,
        ocr_engine=ocr_engine_enum,
        ocr_options=ocr_options,
        do_table_structure=True,
        table_structure_options=PdfPipelineOptions().table_structure_options.model_copy(
            update={
                "do_cell_matching": True,
                "mode": TableFormerMode.ACCURATE,
            }
        ),
        generate_page_images=generate_page_images,
        accelerator_options=AcceleratorOptions(
            num_threads=4,
            device=AcceleratorDevice.AUTO,
        ),
    )


def get_image_pipeline_options(
    *,
    lang: str = "eng",
) -> "object":
    """
    Build pipeline options for Docling image conversion.

    Returns format options compatible with DocumentConverter for InputFormat.IMAGE.
    """
    from docling.document_converter import ImageFormatOption

    return ImageFormatOption()
