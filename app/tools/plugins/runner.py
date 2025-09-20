"""Utility executed in a sandboxed subprocess to run a plugin."""

from __future__ import annotations

import argparse
import importlib
import hmac
import os
import sys
from typing import Sequence

from app.tools import plugins

_NETWORK_ENV_FLAG = "WATCHER_BLOCK_NETWORK"


def _disable_network() -> None:
    """Apply coarse network restrictions for Python-based plugins."""

    try:
        import socket
    except Exception:  # pragma: no cover - socket should always be available
        return

    def _deny(*_args: object, **_kwargs: object) -> None:
        raise OSError("Network access is disabled in the Watcher sandbox")

    class _DeniedSocket(socket.socket):  # type: ignore[misc]
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - defensive
            _deny()

    socket.socket = _DeniedSocket  # type: ignore[assignment]
    for name in ("create_connection", "create_server", "socketpair"):
        if hasattr(socket, name):
            setattr(socket, name, _deny)


def _resolve_attribute(module: object, attribute: str) -> object:
    obj = module
    for part in attribute.split("."):
        obj = getattr(obj, part)
    return obj


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a Watcher plugin")
    parser.add_argument("--path", required=True, help="Module path to the plugin class")
    parser.add_argument("--signature", required=True, help="Expected SHA-256 of the module")
    parser.add_argument("--api-version", required=True, help="Plugin API version")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if os.environ.get(_NETWORK_ENV_FLAG) == "1":
        _disable_network()

    args = _parse_args(argv)

    if args.api_version != plugins.SUPPORTED_PLUGIN_API_VERSION:
        raise SystemExit(f"Unsupported API version {args.api_version}")

    module_name, _, attribute = args.path.partition(":")
    if not module_name or not attribute:
        raise SystemExit("Invalid plugin path")

    actual_signature = plugins.compute_module_signature(module_name)
    if actual_signature is None or not hmac.compare_digest(actual_signature, args.signature):
        raise SystemExit("Plugin signature validation failed")

    module = importlib.import_module(module_name)
    plugin_cls = _resolve_attribute(module, attribute)
    plugin = plugin_cls()
    result = plugin.run()
    sys.stdout.write(str(result))
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
