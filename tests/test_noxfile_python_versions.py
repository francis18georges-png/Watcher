"""Regression tests for the WATCHER_NOX_PYTHON parsing helper."""

from __future__ import annotations

import importlib
import sys
import types

try:
    import nox  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised when nox is unavailable
    nox = types.ModuleType("nox")

    def session(*args: object, **kwargs: object):
        def decorator(function):
            return function

        return decorator

    nox.session = session  # type: ignore[attr-defined]
    nox.options = types.SimpleNamespace(sessions=(), reuse_existing_virtualenvs=False)  # type: ignore[attr-defined]
    sys.modules["nox"] = nox

    command_module = types.ModuleType("nox.command")

    class CommandFailed(RuntimeError):
        pass

    command_module.CommandFailed = CommandFailed  # type: ignore[attr-defined]
    sys.modules["nox.command"] = command_module

import noxfile


def test_parse_python_versions_defaults_when_missing() -> None:
    assert noxfile._parse_python_versions(None) == ["3.12"]


def test_parse_python_versions_accepts_commas_and_whitespace() -> None:
    value = "3.10, 3.11\n3.12"
    assert noxfile._parse_python_versions(value) == ["3.10", "3.11", "3.12"]


def test_parse_python_versions_discards_empty_tokens() -> None:
    value = "  \t , ,  "
    assert noxfile._parse_python_versions(value) == ["3.12"]


def test_get_python_versions_uses_environment(monkeypatch) -> None:
    monkeypatch.setenv("WATCHER_NOX_PYTHON", "3.11,3.9 3.10")
    importlib.reload(noxfile)
    try:
        assert noxfile.get_python_versions() == ["3.11", "3.9", "3.10"]
        assert noxfile.PYTHON_VERSIONS == ["3.11", "3.9", "3.10"]
    finally:
        monkeypatch.delenv("WATCHER_NOX_PYTHON", raising=False)
        importlib.reload(noxfile)
