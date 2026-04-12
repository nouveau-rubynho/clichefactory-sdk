"""
Canonical document metadata stored alongside uploaded documents in S3.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentMetadata(BaseModel):
    """Metadata sidecar for documents stored at tenants/{t}/projects/{p}/documents/{d}/."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    file_name: str
    file_type: str
    content_sha256: str
    size_bytes: int
    uploaded_at: str  # ISO 8601
    source: Literal["inference", "upload", "emio"]
    tenant_id: str
    project_id: str
