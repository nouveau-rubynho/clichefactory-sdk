"""
Canonical training job payload (strict). No flat legacy fields; nested only.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelEndpointPayload(BaseModel):
    """Single LLM endpoint config."""

    model_config = ConfigDict(extra="forbid")

    provider_model: str | None = None
    api_key: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    num_retries: int | None = Field(default=None, ge=0)
    api_base: str | None = None


class DatasetPayload(BaseModel):
    """Dataset locations and input mode."""

    model_config = ConfigDict(extra="forbid")

    input_uri: str = ""
    ground_truth_uri: str = ""
    input_mode: Literal["markdown", "media"] = "markdown"


class ModelPayload(BaseModel):
    """Model config: flat extraction/ocr/trainer or nested endpoints."""

    model_config = ConfigDict(extra="forbid")

    provider_model: str | None = None
    api_key: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    num_retries: int | None = Field(default=None, ge=0)
    api_base: str | None = None
    ocr_provider_model: str | None = None
    ocr_api_key: str | None = None
    ocr_max_tokens: int | None = Field(default=None, gt=0)
    ocr_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    trainer_provider_model: str | None = None
    trainer_api_key: str | None = None
    trainer_max_tokens: int | None = Field(default=None, gt=0)
    trainer_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    extraction: ModelEndpointPayload | None = None
    ocr: ModelEndpointPayload | None = None
    trainer: ModelEndpointPayload | None = None


class ParsingPayload(BaseModel):
    """Parsing options (PDF/image, etc.)."""

    model_config = ConfigDict(extra="forbid")

    input_mode: Literal["markdown", "media"] | None = None
    pdf_image_parser: Literal[
        "docling", "docling_vlm", "yolo_per_partes"
    ] | None = None
    pdf_fallback_to_ocr_llm: bool | None = None
    pdf_structured_fallback_to_image: bool | None = None
    pdf_ocr_engine: Literal["tesseract", "rapidocr", "easyocr"] | None = None
    pdf_ocr_lang: str | None = None
    use_ocr_llm_body: bool | None = None
    image_parser: Literal["pytesseract", "rapidocr", "docling", "ocr_llm"] | None = None
    image_parser_fallback: bool | None = None
    image_parser_lang: str | None = None


class SchemaPayload(BaseModel):
    """Schema for training: name + schema dict (canonical JSON Schema)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = "TrainingSchema"
    schema_: dict[str, Any] = Field(
        default_factory=dict,
        alias="schema",
        serialization_alias="schema",
    )


class TrainingPayload(BaseModel):
    """Training hyperparameters and options."""

    model_config = ConfigDict(extra="forbid")

    optimizer: Literal["auto", "mipro", "gepa"] | None = None
    metric: Literal["exact", "fuzzy"] | None = None
    metric_scope: Literal["aggregate", "per_field"] | None = None
    metric_kind: Literal[
        "graduated_pydantic",
        "graduated_pydantic_item",
        "graduated_pydantic_fuzzy",
        "graduated_pydantic_fuzzy_item",
    ] | None = None
    verifier_enabled: bool | None = None
    dev_split: float | None = Field(default=None, gt=0.0, lt=1.0)
    llm_max_tokens: int | None = Field(default=None, gt=0)
    llm_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    llm_num_retries: int | None = Field(default=None, ge=0)
    trainer_model_max_tokens: int | None = Field(default=None, gt=0)
    trainer_model_temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class TrackingPayload(BaseModel):
    """Experiment tracking (e.g. MLflow)."""

    model_config = ConfigDict(extra="forbid")

    experiment_name: str | None = None


class TrainingJobPayloadV1(BaseModel):
    """
    Canonical training job payload. Strict; no flat legacy fields.
    Adapters map legacy flat fields into nested model/parsing/training.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dataset: DatasetPayload = Field(default_factory=DatasetPayload)
    schema_: SchemaPayload | None = Field(default=None, alias="schema")
    model_schema: SchemaPayload | None = None
    model: ModelPayload = Field(default_factory=ModelPayload)
    parsing: ParsingPayload | None = None
    training: TrainingPayload = Field(default_factory=TrainingPayload)
    tracking: TrackingPayload = Field(default_factory=TrackingPayload)
    trained_module_path: str | None = None
    artifact_uri: str | None = None
    model_name: str | None = None
