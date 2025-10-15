"""Minimal pytest-socket replacement used for offline CI.

This module provides a tiny subset of the `pytest-socket` plugin so that
`--disable-socket` and related options remain available even when the official
package cannot be installed (for example in restricted build environments).
"""

from __future__ import annotations

import socket
from typing import Iterable


class SocketBlockedError(RuntimeError):
    """Raised when a test unexpectedly performs a network operation."""


class _SocketGuard:
    """Runtime helpers for socket blocking."""

    allowed_hosts: set[str]
    allow_unix: bool
    enabled: bool
    real_socket = socket.socket
    real_create_connection = socket.create_connection

    @classmethod
    def configure(cls, allow_unix: bool, hosts: Iterable[str]) -> None:
        cls.allow_unix = allow_unix
        cls.allowed_hosts = {host.strip() for host in hosts if host.strip()}

    @classmethod
    def enable(cls) -> None:
        if getattr(cls, "enabled", False):
            return

        class BlockingSocket(cls.real_socket):  # type: ignore[misc]
            def connect(self, address):  # type: ignore[override]
                _check_allowed(address, self.family)
                return super().connect(address)

            def connect_ex(self, address):  # type: ignore[override]
                _check_allowed(address, self.family)
                return super().connect_ex(address)

        def guarded_create_connection(address, *args, **kwargs):  # type: ignore[override]
            _check_allowed(address, socket.AF_INET)
            return cls.real_create_connection(address, *args, **kwargs)

        socket.socket = BlockingSocket  # type: ignore[assignment]
        socket.create_connection = guarded_create_connection  # type: ignore[assignment]
        cls.enabled = True

    @classmethod
    def disable(cls) -> None:
        if not getattr(cls, "enabled", False):
            return
        socket.socket = cls.real_socket  # type: ignore[assignment]
        socket.create_connection = cls.real_create_connection  # type: ignore[assignment]
        cls.enabled = False


def _check_allowed(address, family: int) -> None:
    if family == getattr(socket, "AF_UNIX", object()) and _SocketGuard.allow_unix:
        return

    host = None
    if isinstance(address, str):
        host = address
    elif isinstance(address, tuple) and address:
        host = address[0]

    if host and host in _SocketGuard.allowed_hosts:
        return

    raise SocketBlockedError("Network access is disabled by the pytest_socket shim.")


def pytest_addoption(parser) -> None:
    group = parser.getgroup("socket")
    group.addoption(
        "--disable-socket",
        action="store_true",
        help="Interdit toute ouverture de socket réseau pendant les tests.",
    )
    group.addoption(
        "--allow-unix-socket",
        action="store_true",
        default=False,
        help="Autorise les sockets UNIX lorsque le réseau est désactivé.",
    )
    group.addoption(
        "--allow-hosts",
        action="append",
        default=[],
        help="Liste d'hôtes autorisés malgré la désactivation globale du réseau.",
    )


def pytest_configure(config) -> None:
    if not config.getoption("--disable-socket"):
        return
    _SocketGuard.configure(
        allow_unix=config.getoption("--allow-unix-socket"),
        hosts=config.getoption("--allow-hosts") or [],
    )
    _SocketGuard.enable()
    config._socket_guard_enabled = True  # type: ignore[attr-defined]


def pytest_unconfigure(config) -> None:
    if getattr(config, "_socket_guard_enabled", False):
        _SocketGuard.disable()


def disable_socket(allow_unix_socket: bool = False, allow_hosts: Iterable[str] | None = None) -> None:
    """Public helper mirroring the upstream plugin API."""

    _SocketGuard.configure(allow_unix_socket, allow_hosts or [])
    _SocketGuard.enable()


def enable_socket() -> None:
    """Restore the original socket module."""

    _SocketGuard.disable()
