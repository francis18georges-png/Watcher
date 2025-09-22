"""Shared pytest fixtures for the Watcher test suite."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

import pytest

try:  # pragma: no cover - exercised during test collection
    import pytest_socket as socket
except ImportError:  # pragma: no cover - fallback when dependency missing locally
    import socket as stdlib_socket

    _original_socket = stdlib_socket.socket
    _original_create_connection = stdlib_socket.create_connection

    class SocketBlockedError(RuntimeError):
        """Raised when a test unexpectedly performs a network operation."""

    def _blocked_socket(*args, **kwargs):
        raise SocketBlockedError("Network access is disabled during tests")

    def _blocked_create_connection(*args, **kwargs):
        raise SocketBlockedError("Network access is disabled during tests")

    def disable_socket() -> None:
        stdlib_socket.socket = _blocked_socket  # type: ignore[assignment]
        stdlib_socket.create_connection = _blocked_create_connection  # type: ignore[assignment]

    def enable_socket() -> None:
        stdlib_socket.socket = _original_socket  # type: ignore[assignment]
        stdlib_socket.create_connection = _original_create_connection  # type: ignore[assignment]

    socket = ModuleType("pytest_socket")
    socket.disable_socket = disable_socket  # type: ignore[attr-defined]
    socket.enable_socket = enable_socket  # type: ignore[attr-defined]
    socket.SocketBlockedError = SocketBlockedError  # type: ignore[attr-defined]
    sys.modules.setdefault("pytest_socket", socket)

pytest_plugins = ("pytest_socket",)

socket.disable_socket()


@pytest.fixture(autouse=True)
def configure_logging() -> None:
    """Reset logging configuration so caplog captures expected records."""

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    logger_states: dict[logging.Logger, tuple[bool, int]] = {}
    for existing in logging.root.manager.loggerDict.values():
        if isinstance(existing, logging.Logger):
            logger_states[existing] = (existing.disabled, existing.level)
    for handler in original_handlers:
        root.removeHandler(handler)
    logging.basicConfig(level=logging.INFO)
    for existing in logger_states:
        existing.disabled = False
        existing.setLevel(logging.NOTSET)
    try:
        yield
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)
        for logger_obj, (disabled, level) in logger_states.items():
            logger_obj.disabled = disabled
            logger_obj.setLevel(level)


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
