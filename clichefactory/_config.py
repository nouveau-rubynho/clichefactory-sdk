"""
CLI configuration file management.

Reads/writes ~/.clichefactory/config.toml.  Config precedence (highest first):
    1. CLI flags
    2. Environment variables
    3. Config file (~/.clichefactory/config.toml)
    4. Defaults
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


_CONFIG_DIR = Path.home() / ".clichefactory"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"


@dataclass
class ServiceConfig:
    api_key: str = ""
    base_url: str = ""

@dataclass
class LocalConfig:
    model: str = ""
    api_key: str = ""
    ocr_model: str = ""
    ocr_api_key: str = ""

@dataclass
class CLIConfig:
    default_mode: str = "service"
    service: ServiceConfig = field(default_factory=ServiceConfig)
    local: LocalConfig = field(default_factory=LocalConfig)


def config_dir() -> Path:
    return _CONFIG_DIR


def config_file_path() -> Path:
    return _CONFIG_FILE


def load_config() -> CLIConfig:
    """Load config from ~/.clichefactory/config.toml. Returns defaults if file doesn't exist."""
    cfg = CLIConfig()
    if not _CONFIG_FILE.is_file():
        return cfg

    with open(_CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)

    cfg.default_mode = data.get("default_mode", cfg.default_mode)

    if "service" in data:
        s = data["service"]
        cfg.service.api_key = s.get("api_key", "")
        cfg.service.base_url = s.get("base_url", "")

    if "local" in data:
        lo = data["local"]
        cfg.local.model = lo.get("model", "")
        cfg.local.api_key = lo.get("api_key", "")
        cfg.local.ocr_model = lo.get("ocr_model", "")
        cfg.local.ocr_api_key = lo.get("ocr_api_key", "")

    return cfg


def save_config(cfg: CLIConfig) -> Path:
    """Write config to ~/.clichefactory/config.toml. Returns the path written."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f'default_mode = "{cfg.default_mode}"')
    lines.append("")

    lines.append("[service]")
    lines.append(f'api_key = "{cfg.service.api_key}"')
    if cfg.service.base_url:
        lines.append(f'base_url = "{cfg.service.base_url}"')
    lines.append("")

    lines.append("[local]")
    lines.append(f'model = "{cfg.local.model}"')
    lines.append(f'api_key = "{cfg.local.api_key}"')
    if cfg.local.ocr_model:
        lines.append(f"")
        lines.append(f"# Optional: separate model for OCR/VLM tasks (image-to-text).")
        lines.append(f"# If not set, the main model is used for everything.")
        lines.append(f"# Only needed when you want a cheaper/faster model for OCR")
        lines.append(f"# while keeping a more capable model for extraction.")
        lines.append(f'ocr_model = "{cfg.local.ocr_model}"')
    if cfg.local.ocr_api_key and cfg.local.ocr_api_key != cfg.local.api_key:
        lines.append(f'ocr_api_key = "{cfg.local.ocr_api_key}"')
    lines.append("")

    _CONFIG_FILE.write_text("\n".join(lines), encoding="utf-8")
    return _CONFIG_FILE


def resolve_api_key(*, cli_flag: str | None, cfg: CLIConfig) -> str:
    """Resolve ClicheFactory service API key: CLI flag > env > config file."""
    if cli_flag:
        return cli_flag
    env = os.environ.get("CLICHEFACTORY_API_KEY", "")
    if env:
        return env
    return cfg.service.api_key


def resolve_base_url(*, cli_flag: str | None, cfg: CLIConfig) -> str | None:
    """Resolve service base URL: CLI flag > env > config file > None."""
    if cli_flag:
        return cli_flag
    env = os.environ.get("CLICHEFACTORY_API_URL", "")
    if env:
        return env
    return cfg.service.base_url or None


def resolve_model(*, cli_flag: str | None, cfg: CLIConfig) -> str:
    """Resolve LLM model name: CLI flag > env > config file."""
    if cli_flag:
        return cli_flag
    env = os.environ.get("CLICHEFACTORY_LLM_MODEL_NAME") or os.environ.get("LLM_MODEL_NAME", "")
    if env:
        return env
    return cfg.local.model


def resolve_model_api_key(*, cli_flag: str | None, cfg: CLIConfig) -> str:
    """Resolve LLM API key: CLI flag > env > config file."""
    if cli_flag:
        return cli_flag
    env = os.environ.get("CLICHEFACTORY_LLM_API_KEY") or os.environ.get("LLM_API_KEY", "")
    if env:
        return env
    return cfg.local.api_key


def resolve_ocr_model(*, cli_flag: str | None, cfg: CLIConfig) -> str:
    """Resolve OCR model name: CLI flag > env > config file > main model."""
    if cli_flag:
        return cli_flag
    env = os.environ.get("CLICHEFACTORY_OCR_MODEL_NAME") or os.environ.get("OCR_MODEL_NAME", "")
    if env:
        return env
    return cfg.local.ocr_model


def resolve_ocr_api_key(*, cli_flag: str | None, cfg: CLIConfig, model_api_key: str) -> str:
    """Resolve OCR API key: CLI flag > env > config file > main model key."""
    if cli_flag:
        return cli_flag
    env = os.environ.get("CLICHEFACTORY_OCR_API_KEY") or os.environ.get("OCR_API_KEY", "")
    if env:
        return env
    return cfg.local.ocr_api_key or model_api_key
