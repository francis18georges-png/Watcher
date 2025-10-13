"""Tests ensuring downloadable model artifacts are validated strictly."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.core import model_registry as registry


def _spec(tmp_path: Path, content: bytes) -> registry.ModelSpec:
    sha = hashlib.sha256(content).hexdigest()
    return registry.ModelSpec(
        name="demo.bin",
        sha256=sha,
        size_bytes=len(content),
        urls=("https://example.com/demo.bin",),
        license="Apache-2.0",
        family="demo",
        backend="llama.cpp",
        context_size=2048,
        description="test",
    )


def test_download_model_retries_when_size_does_not_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = b"correct-content"
    spec = _spec(tmp_path, content)
    base_dir = tmp_path / "models"
    base_dir.mkdir()
    destination = base_dir / spec.name
    destination.write_bytes(content[:-1])

    original_hash = registry._hash_file

    def fake_hash(path: Path) -> str:
        if path == destination:
            return spec.sha256
        return original_hash(path)

    monkeypatch.setattr(registry, "_hash_file", fake_hash)

    calls: list[str] = []

    def fake_download(url: str, target: Path, resume: bool) -> bool:
        calls.append(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return True

    monkeypatch.setattr(registry, "_download_once", fake_download)

    path = registry.download_model(spec, base_dir)

    assert path.read_bytes() == content
    assert calls == ["https://example.com/demo.bin"]


def test_artifact_matches_spec_checks_size(tmp_path: Path) -> None:
    content = b"data"
    spec = _spec(tmp_path, content)
    path = tmp_path / spec.name
    path.write_bytes(content)
    assert registry._artifact_matches_spec(path, spec) is True

    spec_mismatch = registry.ModelSpec(
        name=spec.name,
        sha256=spec.sha256,
        size_bytes=len(content) + 1,
        urls=spec.urls,
        license=spec.license,
        family=spec.family,
        backend=spec.backend,
        context_size=spec.context_size,
        description=spec.description,
    )

    assert registry._artifact_matches_spec(path, spec_mismatch) is False

