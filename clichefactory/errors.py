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

