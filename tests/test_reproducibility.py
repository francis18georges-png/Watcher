from __future__ import annotations

import os
import random

from app import cli
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


def _run_cli_and_sample(args: list[str]) -> tuple[dict[str, str | None], list[float]]:
    random.seed(999)
    exit_code = cli.main(args)
    assert exit_code == 0
    env_values = {
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "WATCHER_TRAINING__SEED": os.environ.get("WATCHER_TRAINING__SEED"),
    }
    return env_values, [random.random() for _ in range(3)]


def test_cli_reproducibility_end_to_end(monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("WATCHER_TRAINING__SEED", "0")

    env_values, seq1 = _run_cli_and_sample(["plugin", "list"])
    assert env_values == {
        "PYTHONHASHSEED": "42",
        "WATCHER_TRAINING__SEED": "42",
    }

    env_values_repeat, seq2 = _run_cli_and_sample(["plugin", "list"])
    assert env_values_repeat == env_values
    assert seq1 == seq2

    env_custom, seq_custom1 = _run_cli_and_sample([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_custom == {
        "PYTHONHASHSEED": "123",
        "WATCHER_TRAINING__SEED": "123",
    }

    env_custom_repeat, seq_custom2 = _run_cli_and_sample([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_custom_repeat == env_custom
    assert seq_custom1 == seq_custom2
