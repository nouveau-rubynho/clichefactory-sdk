"""Optional usage tracker protocol for server-side cost accounting."""

from __future__ import annotations

from typing import Protocol


class UsageTracker(Protocol):
    def add_ocr_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        thinking_tokens: int = 0,
    ) -> None: ...

    def add_extraction_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        thinking_tokens: int = 0,
    ) -> None: ...
