"""
Canonical deployment payloads. Scope and artifact_id live on envelope scope/resource.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeploymentRollout(BaseModel):
    """Rollout mode for activation."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["immediate"] = "immediate"


class ActivateDeploymentPayload(BaseModel):
    """Payload for deployment.activate. artifact_id and scope come from envelope."""

    model_config = ConfigDict(extra="forbid")

    rollout: DeploymentRollout = Field(default_factory=DeploymentRollout)
