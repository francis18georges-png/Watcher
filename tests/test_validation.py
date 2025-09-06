import pytest
from pathlib import Path

from app.core.validation import validate_prompt, validate_dataset


def test_validate_prompt_ok():
    assert validate_prompt("hello") == "hello"


def test_validate_prompt_empty():
    with pytest.raises(ValueError):
        validate_prompt("   ")


def test_validate_prompt_type():
    with pytest.raises(TypeError):
        validate_prompt(123)  # type: ignore[arg-type]


def _make_dataset(tmp_path: Path) -> Path:
    d = tmp_path / "task"
    d.mkdir()
    (d / "src").mkdir()
    (d / "tests").mkdir()
    (d / "meta.json").write_text("{}")
    return d


def test_validate_dataset_ok(tmp_path):
    d = _make_dataset(tmp_path)
    assert validate_dataset(d) == d


def test_validate_dataset_missing_meta(tmp_path):
    d = tmp_path / "task"
    d.mkdir()
    (d / "src").mkdir()
    (d / "tests").mkdir()
    with pytest.raises(ValueError):
        validate_dataset(d)


def test_validate_dataset_missing_tests(tmp_path):
    d = tmp_path / "task"
    d.mkdir()
    (d / "src").mkdir()
    (d / "meta.json").write_text("{}")
    with pytest.raises(ValueError):
        validate_dataset(d)


def test_validate_dataset_not_exists(tmp_path):
    with pytest.raises(ValueError):
        validate_dataset(tmp_path / "missing")
