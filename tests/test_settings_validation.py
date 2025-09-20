from pathlib import Path

import pytest
from pydantic import ValidationError

from app.configuration import (
    LLMSettings,
    MemorySettings,
    PathsSettings,
    SandboxSettings,
)


def test_llm_ctx_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        LLMSettings(ctx=0)


def test_memory_cache_size_positive() -> None:
    with pytest.raises(ValidationError):
        MemorySettings(cache_size=0)


def test_sandbox_timeout_positive() -> None:
    with pytest.raises(ValidationError):
        SandboxSettings(timeout_seconds=0)


def test_paths_resolve_relative(tmp_path: Path) -> None:
    paths = PathsSettings(base_dir=tmp_path)
    resolved = paths.resolve(Path("subdir") / "file.txt")
    assert resolved == (tmp_path / "subdir" / "file.txt").resolve()
