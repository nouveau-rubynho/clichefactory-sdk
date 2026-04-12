"""
Deterministic hashing for cache key derivation (model_schema, parser_config).
"""
from __future__ import annotations

import hashlib
import json


def _canonical_json_dumps(obj: object) -> str:
    """Sort keys and compact separators for deterministic serialization."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def hash_model_schema(schema: dict) -> str:
    """Deterministic SHA-256 hash of canonical JSON serialization of the schema."""
    return hashlib.sha256(_canonical_json_dumps(schema).encode()).hexdigest()


def hash_parser_config(config: dict) -> str:
    """Deterministic SHA-256 hash of canonical JSON serialization of parsing config."""
    return hashlib.sha256(_canonical_json_dumps(config).encode()).hexdigest()
