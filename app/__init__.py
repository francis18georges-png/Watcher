"""Watcher application package."""

from __future__ import annotations

from app.core import logging_setup

__all__ = ["__version__"]

__version__ = "0.1.0"

logging_setup.configure()
