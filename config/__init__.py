from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load configuration from ``settings.toml``.

    Returns
    -------
    dict
        Parsed configuration dictionary. If the file cannot be read an empty
        dictionary is returned.
    """
    cfg_path = Path(__file__).resolve().parent / "settings.toml"
    try:
        with cfg_path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}
