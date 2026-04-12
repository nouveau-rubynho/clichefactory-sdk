"""Backward-compatible re-export of S3 key-builder helpers.

These utilities live in ``clichefactory_internal.contracts.key_builder`` and
are re-exported here so that internal services can import from
``clichefactory._engine.contracts.key_builder``.
"""

try:
    from clichefactory_internal.contracts.key_builder import (
        CacheNamespace,
        artifact_key_from_envelope,
        artifact_uri_from_envelope,
        build_artifact_key,
        build_artifact_metadata_key,
        build_artifact_prefix,
        build_cache_key,
        build_content_index_key,
        build_document_key,
        build_document_metadata_key,
        build_document_prefix,
        build_s3_uri,
        build_training_dataset_prefix,
        cache_key_from_envelope,
        parse_s3_uri,
        resolve_bucket,
    )
except ImportError:
    pass

__all__ = [
    "CacheNamespace",
    "artifact_key_from_envelope",
    "artifact_uri_from_envelope",
    "build_artifact_key",
    "build_artifact_metadata_key",
    "build_artifact_prefix",
    "build_cache_key",
    "build_content_index_key",
    "build_document_key",
    "build_document_metadata_key",
    "build_document_prefix",
    "build_s3_uri",
    "build_training_dataset_prefix",
    "cache_key_from_envelope",
    "parse_s3_uri",
    "resolve_bucket",
]
