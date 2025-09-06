from __future__ import annotations

from pathlib import Path

import pytest

from app.data import validate_dataset


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    dataset = tmp_path / "task"
    dataset.mkdir()
    (dataset / "src").mkdir()
    (dataset / "tests").mkdir()
    (dataset / "meta.json").write_text("{}", encoding="utf-8")
    return dataset


def test_validate_dataset_accepts_complete_dataset(dataset: Path) -> None:
    validate_dataset(dataset)


@pytest.mark.parametrize("missing_dir", ["src", "tests"])
def test_validate_dataset_requires_directories(dataset: Path, missing_dir: str) -> None:
    (dataset / missing_dir).rmdir()
    with pytest.raises(ValueError):
        validate_dataset(dataset)


def test_validate_dataset_requires_meta(dataset: Path) -> None:
    (dataset / "meta.json").unlink()
    with pytest.raises(ValueError):
        validate_dataset(dataset)
