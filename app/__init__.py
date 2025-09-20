"""Watcher application package."""

from __future__ import annotations

import logging

from app.core import logging_setup

try:
    logging_setup.configure()
except ImportError as exc:  # pragma: no cover - defensive fallback
    if "partially initialized module 'config'" not in str(exc):
        raise
    logging.basicConfig(level=logging.INFO)
