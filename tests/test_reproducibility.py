from __future__ import annotations

import random

from app.core.reproducibility import set_seed

try:  # NumPy may be a lightweight stub without RNG support
    import numpy as np

    HAS_NUMPY_RNG = hasattr(np, "random") and hasattr(np.random, "rand")
except Exception:  # pragma: no cover - optional dependency
    np = None  # type: ignore[assignment]
    HAS_NUMPY_RNG = False


def test_set_seed_reproducible():
    set_seed(123)
    py_vals = [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        np_vals = np.random.rand(3)

    set_seed(123)
    assert py_vals == [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        assert np.allclose(np_vals, np.random.rand(3))
