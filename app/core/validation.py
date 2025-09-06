from __future__ import annotations

"""Validation utilities for user prompts and training datasets."""

from pathlib import Path


def validate_prompt(prompt: str) -> str:
    """Ensure *prompt* is a non-empty string.

    Parameters
    ----------
    prompt:
        Input provided by the user.

    Returns
    -------
    str
        The validated prompt.

    Raises
    ------
    TypeError
        If *prompt* is not a string.
    ValueError
        If *prompt* is empty or only whitespace.
    """

    if not isinstance(prompt, str):  # type: ignore[unreachable]
        raise TypeError("prompt must be a string")
    if not prompt.strip():
        raise ValueError("prompt cannot be empty")
    return prompt


def validate_dataset(path: Path | str) -> Path:
    """Validate that *path* points to a dataset directory.

    The directory must exist and contain ``meta.json`` as well as ``src`` and
    ``tests`` sub-directories.

    Parameters
    ----------
    path:
        Filesystem path to the dataset.

    Returns
    -------
    pathlib.Path
        The resolved dataset path.

    Raises
    ------
    ValueError
        If the path does not exist or required files are missing.
    """

    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise ValueError("dataset path not found")
    if not (p / "meta.json").exists():
        raise ValueError("dataset missing meta.json")
    if not (p / "src").is_dir():
        raise ValueError("dataset missing src directory")
    if not (p / "tests").is_dir():
        raise ValueError("dataset missing tests directory")
    return p
