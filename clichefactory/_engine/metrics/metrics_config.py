"""
MetricsConfig: load field_weights and field_fuzzy_config from YAML.
Merge with defaults: fields not in field_weights get uniform share;
fields not in field_fuzzy_config are strict (threshold 1.0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class MetricsConfig:
    """Field weights and per-field fuzzy thresholds for metrics."""

    field_weights: dict[str, float] = field(default_factory=dict)
    field_fuzzy_config: dict[str, float] = field(default_factory=dict)


def load_metrics_config(path: str | Path | None) -> MetricsConfig:
    """
    Load metrics config from YAML.
    Returns MetricsConfig with field_weights and field_fuzzy_config.
    If path is None or file missing, returns empty config (all defaults).
    """
    if path is None:
        return MetricsConfig()
    path = Path(path)
    if not path.exists():
        return MetricsConfig()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return MetricsConfig(
        field_weights=data.get("field_weights", {}),
        field_fuzzy_config=data.get("field_fuzzy_config", {}),
    )
