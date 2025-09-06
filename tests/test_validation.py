from __future__ import annotations

from pathlib import Path
import pytest

from app.data import validate_dataset


@pytest.fixture
def dataset_missing_src(tmp_path: Path) -> Path:
    dataset = tmp_path / "task"
    dataset.mkdir()
    (dataset / "tests").mkdir()
    (dataset / "meta.json").write_text("{}", encoding="utf-8")
    return dataset


def test_validate_dataset_requires_src(dataset_missing_src: Path) -> None:
    with pytest.raises(ValueError):
        validate_dataset(dataset_missing_src)
