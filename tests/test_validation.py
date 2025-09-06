import pytest

from app.core.validation import validate_prompt


def test_validate_prompt_valid() -> None:
    assert validate_prompt("Hello") == "Hello"


def test_validate_prompt_empty() -> None:
    # Capture the exception so we can assert on the error message
    with pytest.raises(ValueError) as exc_info:
        validate_prompt("")
    assert "Prompt cannot be empty" in str(exc_info.value)


def test_validate_prompt_type() -> None:
    # Ensure the type error message clearly indicates the problem
    with pytest.raises(TypeError) as exc_info:
        validate_prompt(123)
    assert "Prompt must be a string" in str(exc_info.value)
