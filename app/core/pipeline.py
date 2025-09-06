from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Sequence
import logging


def load_raw_data(path: str | Path) -> list[str]:
    """Read *path* and return non-empty stripped lines.

    The function validates that *path* exists and points to a text file with a
    ``.txt`` extension before attempting to read it. Clear log messages are
    emitted when the file is missing or has an unexpected format.
    """

    p = Path(path)
    if not p.exists():
        logging.error("raw data file '%s' does not exist", p)
        raise FileNotFoundError(p)
    if not p.is_file() or p.suffix.lower() != ".txt":
        logging.error("raw data file '%s' has unsupported format", p)
        raise ValueError(f"unsupported file format: {p}")
    try:
        text = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("failed to read raw data file '%s'", p)
        raise exc
    return [line.strip() for line in text if line.strip()]


def normalize_and_dedup(lines: Iterable[str]) -> list[str]:
    """Return normalised unique values from *lines*.

    Leading/trailing whitespace is stripped, content lower-cased and empty
    entries removed.  Order of first appearance is preserved while duplicates
    are discarded.
    """

    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        norm = line.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    return result


def apply_hooks(
    lines: list[str], hooks: Sequence[Callable[[list[str]], list[str]]]
) -> list[str]:
    """Run *hooks* sequentially over ``lines``.

    Each hook receives and returns a list of strings.  Failures are logged and
    ignored so one faulty plug-in does not break the whole pipeline.
    """

    current = list(lines)
    for hook in hooks:
        try:
            current = hook(current)
        except Exception:
            logging.exception(
                "pipeline hook %s failed", getattr(hook, "__name__", hook)
            )
    return current


def stream_raw_data(path: str | Path, *, batch_size: int = 100) -> Iterable[list[str]]:
    """Yield batches of lines from *path* without loading entire file."""

    lines = load_raw_data(path)
    for i in range(0, len(lines), batch_size):
        yield lines[i : i + batch_size]


def transform_data(lines: Iterable[str]) -> list[int]:
    """Convert an iterable of text lines into integers."""
    result: List[int] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        result.append(int(line))
    return result
