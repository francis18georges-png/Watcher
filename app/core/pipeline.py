from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


def load_raw_data(path: str | Path) -> list[str]:
    """Read *path* and return non-empty stripped lines."""
    p = Path(path)
    text = p.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in text if line.strip()]


def transform_data(lines: Iterable[str]) -> list[int]:
    """Convert an iterable of text lines into integers."""
    result: List[int] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        result.append(int(line))
    return result
