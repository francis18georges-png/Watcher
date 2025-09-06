import pytest

from app.core.validation import validate_prompt
from app.data.validation import validate_meta


def test_validate_prompt_valid() -> None:
    assert validate_prompt("Hello") == "Hello"


def test_validate_prompt_empty() -> None:
    with pytest.raises(ValueError):
        validate_prompt("")


def test_validate_prompt_type() -> None:
    with pytest.raises(TypeError):
        validate_prompt(123)


def test_validate_meta_invalid_json(tmp_path) -> None:
    meta = tmp_path / "meta.json"
    meta.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_meta(meta)
