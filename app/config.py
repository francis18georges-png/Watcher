from __future__ import annotations

"""Configuration loader for Watcher."""

from functools import lru_cache
from pathlib import Path
import tomllib

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.toml"


@lru_cache
def load_settings() -> dict:
    """Load settings from the TOML configuration file.

    Returns
    -------
    dict
        Parsed settings as a nested dictionary.
    """
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)
