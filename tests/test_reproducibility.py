from __future__ import annotations

import random

from app.core.reproducibility import set_seed
from app.utils import np

HAS_NUMPY_RNG = hasattr(np, "random") and hasattr(np.random, "rand")


def test_set_seed_reproducible():
    set_seed(123)
    py_vals = [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        np_vals = np.random.rand(3)

    set_seed(123)
    assert py_vals == [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        assert np.allclose(np_vals, np.random.rand(3))
