"""
Canonical operation enum. Used for routing and idempotency (mutating vs read-only).
"""
from __future__ import annotations

from enum import Enum


class Operation(str, Enum):
    """Canonical operations. Mutating ops require idempotency_key."""

    INFERENCE_EXTRACT = "inference.extract"
    TRAINING_CREATE_JOB = "training.create_job"
    TRAINING_GET_JOB = "training.get_job"
    TRAINING_CANCEL_JOB = "training.cancel_job"
    DEPLOYMENT_ACTIVATE = "deployment.activate"
    DEPLOYMENT_RESOLVE = "deployment.resolve"
    ARTIFACT_GET = "artifact.get"

    @property
    def is_mutating(self) -> bool:
        """True if this operation requires idempotency_key."""
        return self in {
            Operation.INFERENCE_EXTRACT,
            Operation.TRAINING_CREATE_JOB,
            Operation.TRAINING_CANCEL_JOB,
            Operation.DEPLOYMENT_ACTIVATE,
        }
