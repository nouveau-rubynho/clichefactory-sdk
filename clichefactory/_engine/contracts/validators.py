"""
Shared field-level validators and helpers for canonical contracts.
"""
from __future__ import annotations

import re
from typing import Any

_SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0"})
_S3_URI_PATTERN = re.compile(r"^s3://[^/]+/.+$")


def validate_s3_uri(uri: str) -> str:
    """Validate that uri is a canonical S3 URI (s3://bucket/key). No presigned URLs."""
    if not uri or not uri.strip():
        raise ValueError("file_uri cannot be empty")
    u = uri.strip()
    if not u.startswith("s3://"):
        raise ValueError("file_uri must be a canonical S3 URI (s3://bucket/key), not a presigned URL")
    if not _S3_URI_PATTERN.match(u):
        raise ValueError("file_uri must match s3://{bucket}/{key}")
    return u


def validate_non_empty_string(v: str) -> str:
    """Strip and ensure non-empty."""
    s = (v if isinstance(v, str) else str(v)).strip()
    if not s:
        raise ValueError("String cannot be empty")
    return s


def validate_schema_version(v: str) -> str:
    """Must be a supported schema version."""
    s = (v if isinstance(v, str) else str(v)).strip()
    if s not in _SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported schema_version: {s}; supported: {sorted(_SUPPORTED_SCHEMA_VERSIONS)}")
    return s


def coerce_id_to_str(v: Any) -> str:
    """Coerce int/uuid/str to str for canonical IDs."""
    if v is None:
        raise ValueError("ID cannot be None")
    return str(v).strip()
