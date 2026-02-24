"""YAML configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class MappingRule(BaseModel):
    """A single group-to-safe mapping rule."""

    group: str
    safe: str
    platform: str | None = None


class AppConfig(BaseModel):
    """Application configuration loaded from YAML."""

    tenant_url: str
    client_id: str
    safe: str | None = None
    mapping_mode: str = "single"
    default_platform: str | None = None
    output_dir: str | None = None
    mapping_rules: list[MappingRule] = Field(default_factory=list)


def load_config(path: Path) -> AppConfig:
    """Load and validate config from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML in {path}: expected a mapping")

    try:
        return AppConfig(**data)
    except ValidationError as exc:
        raise ValueError(f"Config validation error: {exc}") from exc
