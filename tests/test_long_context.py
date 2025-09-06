"""Tests for LLM client context size handling."""

import pytest

from app.llm.client import Client, chunk_prompt


@pytest.mark.parametrize("value", [0, -1])
def test_ctx_must_be_positive(value):
    """Client should reject non-positive context values."""

    with pytest.raises(ValueError):
        Client(ctx=value)


def test_chunk_prompt_preserves_leading_space():
    """Leading whitespace should not be stripped when chunking."""

    prompt = " foo"
    chunks = chunk_prompt(prompt, size=2)
    assert chunks == [" f", "oo"]


def test_chunk_prompt_preserves_trailing_space():
    """Trailing whitespace should be kept in the final chunk."""

    prompt = "foo "
    chunks = chunk_prompt(prompt, size=2)
    assert chunks == ["fo", "o "]

