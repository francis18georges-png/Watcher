from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List


logger = logging.getLogger(__name__)
root_logger = logging.getLogger()


def _logger() -> logging.Logger:
    """Return the module logger ensuring it is enabled."""

    local = logging.getLogger(__name__)
    local.disabled = False
    return local


def _root_logger() -> logging.Logger:
    """Return the root logger ensuring it is enabled."""

    root = logging.getLogger()
    root.disabled = False
    return root


def load_raw_data(path: str | Path) -> list[str]:
    """Read *path* and return non-empty stripped lines.

    The function validates that *path* exists and points to a text file with a
    ``.txt`` extension before attempting to read it. Clear log messages are
    emitted when the file is missing or has an unexpected format.
    """

    p = Path(path)
    if not p.exists():
        _logger().error("raw data file '%s' does not exist", p)
        _root_logger().error("raw data file '%s' does not exist", p)
        raise FileNotFoundError(p)
    if not p.is_file() or p.suffix.lower() != ".txt":
        _logger().error("raw data file '%s' has unsupported format", p)
        _root_logger().error("raw data file '%s' has unsupported format", p)
        raise ValueError(f"unsupported file format: {p}")
    try:
        text = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        _logger().exception("failed to read raw data file '%s'", p)
        _root_logger().exception("failed to read raw data file '%s'", p)
        raise exc
    return [line.strip() for line in text if line.strip()]


def transform_data(lines: Iterable[str]) -> list[int]:
    """Convert an iterable of text lines into integers."""
    result: List[int] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            value = int(line)
        except ValueError:
            _logger().warning("invalid integer '%s'", line)
            _root_logger().warning("invalid integer '%s'", line)
            continue
        result.append(value)
    return result
