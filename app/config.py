from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib


def load_config(section: str | None = None) -> dict[str, Any]:
    """Load configuration from ``config/settings.toml``.

    Args:
        section: Optional top-level section name. When provided only that
            section is returned. If the section does not exist an empty
            dictionary is returned. When omitted the whole configuration is
            returned.
    """
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "settings.toml"
    with cfg_path.open("rb") as fh:
        data = tomllib.load(fh)
    if section is None:
        return data
    return data.get(section, {})
