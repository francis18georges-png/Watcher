"""Simple data preparation pipeline."""

from __future__ import annotations

from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "datasets" / "raw"
PROCESSED_DIR = BASE_DIR / "datasets" / "processed"


def load_raw_data(path: Path | str | None = None) -> dict:
    """Load raw data from ``datasets/raw``.

    Parameters
    ----------
    path:
        Optional path to a JSON file. If not provided, ``RAW_DIR / 'data.json'``
        is used.

    Returns
    -------
    dict
        The parsed JSON content. An empty dictionary is returned when the file
        does not exist.
    """
    p = Path(path) if path else RAW_DIR / "data.json"
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def clean_data(data: dict) -> dict:
    """Remove falsy values from *data*."""
    return {k: v for k, v in data.items() if v}


def transform_data(data: dict, filename: str = "cleaned.json") -> Path:
    """Persist cleaned *data* into ``datasets/processed``.

    Parameters
    ----------
    data:
        Cleaned data to save.
    filename:
        Name of the JSON file to create in the processed directory.

    Returns
    -------
    pathlib.Path
        The path to the written file.
    """
    dest_dir = PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return dest
