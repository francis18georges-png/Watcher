"""Utilities for validating dataset structure."""

from __future__ import annotations

from pathlib import Path


def validate_dataset(path: str | Path) -> Path:
    """Validate that *path* points to a dataset directory.

    A valid dataset directory must contain ``src`` and ``tests`` directories
    as well as a ``meta.json`` file. The function returns the resolved path to
    the dataset when validation succeeds.

    Parameters
    ----------
    path:
        The path to the dataset directory.

    Raises
    ------
    FileNotFoundError
        If the dataset path, ``src`` or ``tests`` directories, or ``meta.json``
        file does not exist. The raised error message includes the offending
        path.
    NotADirectoryError
        If *path* exists but is not a directory.
    """

    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {dataset_path}")
    if not dataset_path.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {dataset_path}")

    src_dir = dataset_path / "src"
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Missing src directory: {src_dir}")

    tests_dir = dataset_path / "tests"
    if not tests_dir.is_dir():
        raise FileNotFoundError(f"Missing tests directory: {tests_dir}")

    meta_file = dataset_path / "meta.json"
    if not meta_file.is_file():
        raise FileNotFoundError(f"Missing meta.json file: {meta_file}")

    return dataset_path.resolve()
