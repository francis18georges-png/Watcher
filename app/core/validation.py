from typing import Any
from pathlib import Path


def validate_prompt(prompt: Any) -> str:
    """Validate that the given prompt is a non-empty string.

    Parameters
    ----------
    prompt: Any
        The user provided prompt to validate.

    Returns
    -------
    str
        The original prompt if it is valid.

    Raises
    ------
    TypeError
        If *prompt* is not an instance of :class:`str`.
    ValueError
        If the prompt is empty or consists solely of whitespace.
    """
    if not isinstance(prompt, str):
        raise TypeError("Prompt must be a string")
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    return prompt


def validate_dataset(path: Any) -> Path:
    """Validate that *path* points to an existing directory.

    Parameters
    ----------
    path:
        Path-like object pointing to the dataset directory to validate.

    Returns
    -------
    pathlib.Path
        The resolved dataset path if it is valid.

    Raises
    ------
    TypeError
        If *path* is not a string or :class:`~pathlib.Path` instance.
    FileNotFoundError
        If the provided path does not exist.
    NotADirectoryError
        If the path exists but is not a directory.
    """
    if not isinstance(path, (str, Path)):
        raise TypeError("Dataset path must be a string or Path")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {p}")
    return p
