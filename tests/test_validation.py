import pytest

from app.core.validation import validate_prompt


def test_validate_prompt_valid() -> None:
    assert validate_prompt("Hello") == "Hello"


def test_validate_prompt_empty() -> None:
    with pytest.raises(ValueError):
        validate_prompt("")


def test_validate_prompt_type() -> None:
    with pytest.raises(TypeError):
        validate_prompt(123)
