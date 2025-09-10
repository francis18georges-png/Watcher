"""Utilities for controlling randomness across the project."""

from __future__ import annotations

import logging
import os
import random

try:  # NumPy is optional
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None  # type: ignore[assignment]


def set_seed(seed: int) -> None:
    """Seed Python, NumPy and other libraries for reproducibility.

    The function configures the :mod:`random` module, ``PYTHONHASHSEED``
    environment variable and, when available, NumPy and PyTorch. It ignores
    missing optional dependencies so that callers can always invoke it without
    guarding import errors.

    Parameters
    ----------
    seed:
        The deterministic seed value used for all RNGs.
    """

    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    if np is not None and hasattr(np, "random") and hasattr(np.random, "seed"):
        np.random.seed(seed)  # type: ignore[attr-defined]
    try:  # pragma: no cover - PyTorch may not be installed
        import torch  # type: ignore[import-not-found]

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:  # pragma: no cover - optional dependency
        pass
    except Exception as exc:  # pragma: no cover - optional dependency
        logging.warning("Failed to seed PyTorch deterministically: %s", exc)
