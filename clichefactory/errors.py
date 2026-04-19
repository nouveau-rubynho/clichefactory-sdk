from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    code: str
    message: str
    hint: str | None = None
    request_id: str | None = None
    retryable: bool | None = None


class ClicheFactoryError(Exception):
    """Base exception for the public `clichefactory` SDK."""

    def __init__(self, info: ErrorInfo):
        super().__init__(info.message)
        self.info = info


class ConfigurationError(ClicheFactoryError):
    pass


class AuthenticationError(ClicheFactoryError):
    pass


class ServiceUnavailableError(ClicheFactoryError):
    pass


class UploadError(ClicheFactoryError):
    pass


class UnsupportedModeError(ClicheFactoryError):
    pass


class UnsupportedParserError(ClicheFactoryError):
    pass


class ParsingError(ClicheFactoryError):
    pass


class ExtractionError(ClicheFactoryError):
    pass


class TrainingError(ClicheFactoryError):
    pass


class ValidationError(ClicheFactoryError):
    pass


class LongExtractionError(ClicheFactoryError):
    """Raised when long-document orchestration fails.

    Error codes:

    - ``long.chunker_failed`` — the ``ChunkStrategy`` raised while splitting.
    - ``long.no_chunks`` — the chunker produced zero chunks.
    - ``long.all_chunks_failed`` — every per-chunk extraction raised.
    - ``long.resolver_failed`` — a resolver callable raised while merging.
    - ``long.unsupported_mode`` — requested mode can't run per-chunk today.
    """

    pass

