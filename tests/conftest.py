"""Shared pytest fixtures for the Watcher test suite."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def psutil_stub(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Provide the lightweight :mod:`psutil` fallback used in tests."""

    try:
        stub = importlib.import_module("app.utils.psutil_stub")
    except Exception:  # pragma: no cover - dependency bootstrap
        module_name = "app.utils.psutil_stub"
        path = Path(__file__).resolve().parents[1] / "app" / "utils" / "psutil_stub.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise ImportError("unable to load psutil_stub module")
        stub = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = stub
        spec.loader.exec_module(stub)
    monkeypatch.setitem(sys.modules, "psutil", stub)
    return stub
