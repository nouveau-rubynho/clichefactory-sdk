from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

PostprocessFn = Callable[[dict[str, Any]], dict[str, Any]]
"""Type alias for a user-supplied postprocessing hook.

A ``PostprocessFn`` is called on the raw extraction result dict *after* the
built-in numeric coercion and *before* Pydantic validation::

    raw LLM dict → [system coerce] → [PostprocessFn] → Pydantic validate

The function receives and must return a ``dict[str, Any]``.  It can modify
values in-place or return a new dict.

Example::

    def normalise_dates(result: dict) -> dict:
        if "invoice_date" in result:
            result["invoice_date"] = parse_date(result["invoice_date"])
        return result

    cliche = client.cliche(Invoice, postprocess=normalise_dates)
"""


@dataclass(frozen=True, slots=True)
class PartialExtraction:
    """Extraction payload when the model output did not fully match the schema.

    Returned when ``allow_partial=True`` and validation failed server-side or
    locally; ``raw`` holds the coerced/postprocessed dict, and
    ``validation_errors`` is the Pydantic error list.
    """

    raw: dict[str, Any]
    validation_errors: list[dict[str, Any]]


class Endpoint(BaseModel):
    """BYOK endpoint configuration (maps to server ModelEndpointPayload)."""

    model_config = ConfigDict(extra="forbid")

    provider_model: str | None = None
    api_key: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    num_retries: int | None = Field(default=None, ge=0)
    api_base: str | None = None


PdfImageParser = Literal["docling", "docling_vlm", "vision_layout"]
PdfOcrEngine = Literal["tesseract", "rapidocr", "easyocr"]
ImageParser = Literal["pytesseract", "rapidocr", "docling", "ocr_llm"]


class ParsingOptions(BaseModel):
    """Public parsing options. Mirrors `aio.config.AioConfig` / server ParsingPayload."""

    model_config = ConfigDict(extra="forbid")

    # PDF
    pdf_image_parser: PdfImageParser | None = None
    pdf_fallback_to_ocr_llm: bool | None = None
    pdf_structured_fallback_to_image: bool | None = None
    pdf_ocr_engine: PdfOcrEngine | None = None
    pdf_ocr_lang: str | None = None
    use_ocr_llm_body: bool | None = None

    # Images
    image_parser: ImageParser | None = None
    image_parser_fallback: bool | None = None
    image_parser_lang: str | None = None


class CostInfo(BaseModel):
    """SDK-facing cost payload (flexible, supports service + BYOK)."""

    model_config = ConfigDict(extra="allow")

    total_usd: float | None = None
    breakdown: dict[str, Any] | None = None


class ExtractMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str | None = None
    mode: str | None = None
    parser: str | None = None
    deployment: dict[str, Any] | None = None


class ExtractEnvelope(BaseModel):
    """Optional rich extract return envelope."""

    model_config = ConfigDict(extra="allow")

    data: dict[str, Any]
    costs: CostInfo | None = None
    document: dict[str, Any] | None = None
    meta: ExtractMeta | None = None


class TrainingMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str | None = None


class TrainingMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    baseline_score_on_dev: float | None = None
    final_score_on_dev: float | None = None
    final_score_full_dataset: float | None = None


class TrainingResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    status: str
    metrics: TrainingMetrics | None = None
    costs: CostInfo | None = None
    meta: TrainingMeta | None = None

