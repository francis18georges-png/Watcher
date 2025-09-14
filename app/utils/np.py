"""Utilities for working with NumPy with a graceful fallback.

This module attempts to import :mod:`numpy`. If it is unavailable, a lightweight
``numpy_stub`` implementation is used instead. A warning is emitted so that
callers are aware that full NumPy functionality is not present.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fallback
    import numpy_stub as np  # type: ignore
    logger.warning("numpy is not installed, using numpy_stub instead")

__all__ = ["np"]
