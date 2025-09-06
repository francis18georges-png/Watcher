from __future__ import annotations

from pathlib import Path


def validate_dataset(path: Path) -> None:
    """Validate that *path* contains ``src``, ``tests`` and ``meta.json``.

    Parameters
    ----------
    path:
        Path to the dataset directory.

    Raises
    ------
    ValueError
        If any required component is missing.
    """
    base = Path(path)
    if not base.is_dir():
        raise ValueError("dataset directory missing")

    required_dirs = ["src", "tests"]
    for name in required_dirs:
        if not (base / name).is_dir():
            raise ValueError(f"missing {name}")

    meta = base / "meta.json"
    if not meta.is_file():
        raise ValueError("missing meta.json")
