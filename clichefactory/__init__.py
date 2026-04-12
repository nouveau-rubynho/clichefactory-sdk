from __future__ import annotations

from clichefactory.__about__ import __version__
from clichefactory.client import Client, factory
from clichefactory.cliche import Cliche
from clichefactory.types import Endpoint, PartialExtraction, ParsingOptions, PostprocessFn
from clichefactory.errors import (
    AuthenticationError,
    ClicheFactoryError,
    ConfigurationError,
    ExtractionError,
    ParsingError,
    ServiceUnavailableError,
    TrainingError,
    UnsupportedModeError,
    UnsupportedParserError,
    UploadError,
    ValidationError,
)

__all__ = [
    "__version__",
    "AuthenticationError",
    "Cliche",
    "ClicheFactoryError",
    "Client",
    "ConfigurationError",
    "Endpoint",
    "ExtractionError",
    "ParsingError",
    "ParsingOptions",
    "PartialExtraction",
    "PostprocessFn",
    "ServiceUnavailableError",
    "TrainingError",
    "UnsupportedModeError",
    "UnsupportedParserError",
    "UploadError",
    "ValidationError",
    "factory",
]

