from pathlib import Path

import pytest
from pydantic import ValidationError

from app.configuration import (
    LLMSettings,
    LoggingSettings,
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


def test_logging_level_must_be_known() -> None:
    with pytest.raises(ValidationError):
        LoggingSettings(fallback_level="invalid")


def test_logging_level_normalised() -> None:
    cfg = LoggingSettings(fallback_level="debug")
    assert cfg.fallback_level == "DEBUG"
