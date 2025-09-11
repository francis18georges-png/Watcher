import pytest

from app.llm.client import chunk_prompt


@pytest.mark.parametrize("size", [0, -1])
def test_chunk_prompt_invalid_size(size: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        chunk_prompt("hello", size=size)
