"""Utilities for validating dataset metadata."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
META_FILE = BASE_DIR / "meta.json"

REQUIRED_KEYS = {"name", "version"}


def validate_meta(path: Path | str | None = None) -> dict[str, Any]:
    """Load and validate a ``meta.json`` file.

    Parameters
    ----------
    path: Path | str | None, optional
        Path to the ``meta.json`` file. Defaults to ``BASE_DIR / 'meta.json'``.

    Returns
    -------
    dict
        Parsed JSON content.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file contains invalid JSON or is missing required keys.
    """
    p = Path(path) if path else META_FILE
    if not p.exists():
        raise FileNotFoundError(f"meta.json not found at {p}")
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError("meta.json contains invalid JSON") from exc

    missing = REQUIRED_KEYS.difference(data)
    if missing:
        raise ValueError(
            f"meta.json missing required keys: {', '.join(sorted(missing))}"
        )
    return data
