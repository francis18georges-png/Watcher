import pytest

from app.core.validation import validate_prompt, validate_dataset


def test_validate_prompt_valid() -> None:
    assert validate_prompt("Hello") == "Hello"


def test_validate_prompt_empty() -> None:
    with pytest.raises(ValueError):
        validate_prompt("")


def test_validate_prompt_type() -> None:
    with pytest.raises(TypeError):
        validate_prompt(123)


def test_validate_dataset_missing(tmp_path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        validate_dataset(missing)
