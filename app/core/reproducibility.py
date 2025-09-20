"""Utilities for controlling randomness across the project."""

from __future__ import annotations

import os
import random

from app.utils import np
from app.core.logging_setup import get_logger


logger = get_logger(__name__)


def set_seed(seed: int) -> None:
    """Seed Python, NumPy and other libraries for reproducibility.

    The function configures the :mod:`random` module, ``PYTHONHASHSEED`` and
    ``WATCHER_TRAINING__SEED`` environment variables and, when available, NumPy
    and PyTorch. It ignores missing optional dependencies so that callers can
    always invoke it without guarding import errors.

    Parameters
    ----------
    seed:
        The deterministic seed value used for all RNGs.
    """

    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["WATCHER_TRAINING__SEED"] = str(seed)
    random.seed(seed)
    if hasattr(np, "random") and hasattr(np.random, "seed"):
        np.random.seed(seed)  # type: ignore[attr-defined]
    try:  # pragma: no cover - PyTorch may not be installed
        import torch  # type: ignore[import-not-found]

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        if hasattr(torch, "use_deterministic_algorithms"):
            torch.use_deterministic_algorithms(True, warn_only=True)
    except ImportError:  # pragma: no cover - optional dependency
        pass
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Failed to seed PyTorch deterministically: %s", exc)
