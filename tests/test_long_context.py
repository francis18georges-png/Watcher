"""Tests for LLM client context size handling."""

import pytest

from app.llm.client import Client


@pytest.mark.parametrize("value", [0, -1])
def test_ctx_must_be_positive(value):
    """Client should reject non-positive context values."""

    with pytest.raises(ValueError):
        Client(ctx=value)

