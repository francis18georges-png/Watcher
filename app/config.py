from __future__ import annotations

from pathlib import Path
from typing import Any
import os

import tomllib


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``."""

    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(section: str | None = None, env: str | None = None) -> dict[str, Any]:
    """Load configuration with optional environment overrides.

    Configuration is read from ``config/settings.toml``.  When *env* or the
    ``WATCHER_ENV`` environment variable is set, values from
    ``config/settings.<env>.toml`` are merged over the base configuration.  This
    allows for automatic selection of development or production settings without
    modifying code.

    Parameters
    ----------
    section:
        Optional top-level section name. When provided only that section is
        returned. If the section does not exist an empty dictionary is returned.
        When omitted the whole configuration is returned.
    env:
        Optional environment name overriding ``WATCHER_ENV``.
    """

    cfg_dir = Path(__file__).resolve().parents[1] / "config"
    with (cfg_dir / "settings.toml").open("rb") as fh:
        data = tomllib.load(fh)

    env_name = env or os.getenv("WATCHER_ENV")
    if env_name:
        env_path = cfg_dir / f"settings.{env_name}.toml"
        if env_path.exists():
            with env_path.open("rb") as fh:
                env_data = tomllib.load(fh)
            data = _deep_merge(data, env_data)

    if section is None:
        return data
    return data.get(section, {})
