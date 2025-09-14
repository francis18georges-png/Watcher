from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import logging
import os
import tomllib

REQUIRED_SECTIONS = {
    "ui",
    "llm",
    "dev",
    "planner",
    "memory",
    "learn",
    "intelligence",
    "data",
    "training",
    "model",
}


logger = logging.getLogger(__name__)


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", path)
        raise
    except tomllib.TOMLDecodeError as exc:
        logger.error("Invalid TOML in %s: %s", path, exc)
        raise


def _deep_update(base: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    for key, value in other.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _validate(cfg: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_SECTIONS - cfg.keys()
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing required sections: {missing_list}")
    for key, value in cfg.items():
        if not isinstance(value, dict):
            raise TypeError(f"Section '{key}' must be a table")
    return cfg


@lru_cache(maxsize=None)
def load_config(profile: str | None = None) -> dict[str, Any]:
    """Load configuration from ``settings.toml`` with optional *profile*.

    Parameters
    ----------
    profile:
        Name of the profile to load. When omitted the value is read from the
        ``WATCHER_PROFILE`` environment variable. Values from
        ``settings.<profile>.toml`` override the base configuration.

    Returns
    -------
    dict
        Parsed and validated configuration dictionary. If the base file cannot
        be read a ``FileNotFoundError`` is raised.
    """

    base_path = Path(__file__).resolve().parent
    cfg_path = base_path / "settings.toml"
    cfg = _read_toml(cfg_path)

    profile = profile or os.getenv("WATCHER_PROFILE")
    if profile:
        try:
            profile_cfg = _read_toml(base_path / f"settings.{profile}.toml")
        except FileNotFoundError:
            logger.warning(
                "Profile configuration file not found: %s",
                base_path / f"settings.{profile}.toml",
            )
            profile_cfg = {}
        cfg = _deep_update(cfg, profile_cfg)

    return _validate(cfg)
