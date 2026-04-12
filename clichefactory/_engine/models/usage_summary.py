"""Provider-agnostic usage summary attached to normalized docs."""

from dataclasses import dataclass, field


@dataclass
class UsageSummary:
    ocr_usd: float = 0.0
    extraction_usd: float = 0.0
    ocr_tokens: dict = field(default_factory=dict)
    extraction_tokens: dict = field(default_factory=dict)
